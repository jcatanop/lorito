"""Grabación con arecord y transcripción local con faster-whisper (CPU, int8)."""

from __future__ import annotations

import subprocess
import threading

import numpy as np

SAMPLE_RATE = 16000
MIN_SECONDS = 0.4


class Recorder:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._chunks: list[bytes] = []
        self._thread: threading.Thread | None = None

    @property
    def recording(self) -> bool:
        return self._proc is not None

    def start(self) -> None:
        self._chunks = []
        self._proc = subprocess.Popen(
            ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-c", "1", "-r", str(SAMPLE_RATE)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self._thread = threading.Thread(target=self._read, args=(self._proc,), daemon=True)
        self._thread.start()

    def _read(self, proc: subprocess.Popen) -> None:
        while chunk := proc.stdout.read(3200):
            self._chunks.append(chunk)

    def stop(self) -> np.ndarray | None:
        """Termina la grabación. Devuelve el audio en float32, o None si fue demasiado corto."""
        if not self._proc:
            return None
        self._proc.terminate()
        self._proc.wait()
        self._thread.join(timeout=1)
        self._proc = None
        pcm = np.frombuffer(b"".join(self._chunks), dtype=np.int16)
        if len(pcm) < SAMPLE_RATE * MIN_SECONDS:
            return None
        return pcm.astype(np.float32) / 32768.0


class Transcriber:
    """Carga el modelo en segundo plano para no retrasar el arranque."""

    def __init__(self, model: str, language: str | None) -> None:
        self.language = language
        self._model = None
        self.error: Exception | None = None
        self._ready = threading.Event()
        threading.Thread(target=self._load, args=(model,), daemon=True).start()

    def _load(self, model: str) -> None:
        try:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(model, device="cpu", compute_type="int8")
        except Exception as exc:
            self.error = exc
        finally:
            self._ready.set()

    @property
    def ready(self) -> bool:
        return self._ready.is_set() and self._model is not None

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _info = self._model.transcribe(
            audio, language=self.language, beam_size=5, vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()
