"""Síntesis de voz local con Piper y reproducción con aplay.

Dos hilos: uno sintetiza frases (adelantándose) y otro las reproduce. Cada frase lleva
la "generación" en la que se encoló; `stop()` incrementa la generación y descarta todo
lo pendiente sin esperar.
"""

from __future__ import annotations

import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from lingua import IsoCode639_1, Language, LanguageDetectorBuilder
from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice

from .textproc import split_sentences

DEFAULT_VOICES = {
    "es": "es_ES-davefx-medium",
    "en": "en_US-lessac-medium",
    "fr": "fr_FR-siwis-medium",
    "pt": "pt_BR-faber-medium",
    "de": "de_DE-thorsten-medium",
    "it": "it_IT-paola-medium",
}

# Por debajo de este tamaño la detección de idioma no es fiable.
MIN_DETECT_CHARS = 25


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    path = Path(base) / "speaker" / "voices"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class _Item:
    gen: int
    text: str
    lang: str


@dataclass
class _Audio:
    gen: int
    pcm: bytes
    rate: int


class Speaker:
    def __init__(self, languages: list[str], voices: dict[str, str], default_lang: str,
                 speed: float = 1.0) -> None:
        self.languages = languages
        self.default_lang = default_lang
        self.voice_names = {lang: voices.get(lang) or DEFAULT_VOICES[lang] for lang in languages}
        self.speed = speed
        self._voices: dict[str, PiperVoice] = {}
        self._last_lang = default_lang
        self._detector = LanguageDetectorBuilder.from_languages(
            *[Language.from_iso_code_639_1(IsoCode639_1.from_str(l)) for l in languages]
        ).with_minimum_relative_distance(0.15).build()

        self._gen = 0
        self._lock = threading.Lock()
        self._text_q: queue.Queue[_Item] = queue.Queue()
        self._audio_q: queue.Queue[_Audio] = queue.Queue(maxsize=4)
        self._resume = threading.Event()
        self._resume.set()
        self._player: subprocess.Popen | None = None
        self._pending = 0  # frases encoladas que aún no terminaron de sonar
        threading.Thread(target=self._synth_loop, daemon=True).start()
        threading.Thread(target=self._play_loop, daemon=True).start()

    # ---- voces -------------------------------------------------------------
    def prepare(self) -> None:
        """Descarga (la primera vez) y carga todas las voces configuradas."""
        for lang in self.languages:
            self._voice(lang)

    def _voice(self, lang: str) -> PiperVoice:
        if lang not in self._voices:
            name = self.voice_names[lang]
            model = data_dir() / f"{name}.onnx"
            if not model.exists() or not model.with_suffix(".onnx.json").exists():
                download_voice(name, data_dir())
            self._voices[lang] = PiperVoice.load(model)
        return self._voices[lang]

    def detect(self, text: str) -> str:
        if len(text) >= MIN_DETECT_CHARS:
            found = self._detector.detect_language_of(text)
            if found is not None:
                self._last_lang = found.iso_code_639_1.name.lower()
        return self._last_lang

    # ---- API pública -------------------------------------------------------
    def say(self, paragraph: str, lang: str | None = None) -> None:
        """Encola un párrafo. Si no se indica idioma, se detecta frase a frase
        (las frases cortas heredan el idioma de la anterior)."""
        with self._lock:
            gen = self._gen
            for sentence in split_sentences(paragraph):
                self._pending += 1
                self._text_q.put(_Item(gen, sentence, lang or self.detect(sentence)))

    def stop(self) -> None:
        """Calla de inmediato y descarta todo lo pendiente."""
        with self._lock:
            self._gen += 1
            self._pending = 0
            for q in (self._text_q, self._audio_q):
                while True:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            self._kill_player()

    def pause(self) -> None:
        """Detiene la lectura; la frase en curso se repetirá al reanudar."""
        self._resume.clear()
        self._kill_player()

    def resume(self) -> None:
        self._resume.set()

    @property
    def busy(self) -> bool:
        return self._pending > 0

    def change_speed(self, delta: float) -> float:
        self.speed = round(min(2.5, max(0.5, self.speed + delta)), 2)
        return self.speed

    def beep(self, freq: float = 880, ms: int = 120) -> None:
        """Pitido corto, fuera de la cola, para señales como empezar a grabar."""
        rate = 22050
        t = np.arange(int(rate * ms / 1000)) / rate
        envelope = np.minimum(1, np.minimum(t, t[::-1]) * 200)
        wave = (0.3 * np.sin(2 * np.pi * freq * t) * envelope * 32767).astype(np.int16)
        _play_pcm(wave.tobytes(), rate)

    # ---- hilos -------------------------------------------------------------
    def _synth_loop(self) -> None:
        while True:
            item = self._text_q.get()
            if item.gen != self._gen:
                continue
            try:
                voice = self._voice(item.lang)
                config = SynthesisConfig(length_scale=1.0 / self.speed)
                pcm = b"".join(c.audio_int16_bytes for c in voice.synthesize(item.text, config))
                rate = voice.config.sample_rate
            except Exception as exc:  # una frase problemática no debe tumbar la lectura
                print(f"\n[speaker] error de síntesis: {exc}", flush=True)
                self._done(item.gen)
                continue
            if item.gen == self._gen:
                self._audio_q.put(_Audio(item.gen, pcm, rate))

    def _play_loop(self) -> None:
        while True:
            audio = self._audio_q.get()
            while audio.gen == self._gen:
                self._resume.wait()
                if audio.gen != self._gen:
                    break
                proc = subprocess.Popen(_aplay_cmd(audio.rate), stdin=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL)
                self._player = proc
                try:
                    proc.stdin.write(audio.pcm)
                    proc.stdin.close()
                except BrokenPipeError:
                    pass
                proc.wait()
                self._player = None
                if proc.returncode == 0:
                    self._done(audio.gen)
                    break
                # Interrumpida por pause(): se repite al reanudar. Por stop(): se descarta.

    def _done(self, gen: int) -> None:
        with self._lock:
            if gen == self._gen and self._pending > 0:
                self._pending -= 1

    def _kill_player(self) -> None:
        proc = self._player
        if proc and proc.poll() is None:
            proc.kill()


def _aplay_cmd(rate: int) -> list[str]:
    return ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-c", "1", "-r", str(rate)]


def _play_pcm(pcm: bytes, rate: int) -> None:
    subprocess.run(_aplay_cmd(rate), input=pcm, stderr=subprocess.DEVNULL, check=False)
