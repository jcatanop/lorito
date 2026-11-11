"""Punto de entrada: `speaker [opciones] claude [argumentos de claude...]`."""

from __future__ import annotations

import argparse
import os
import select
import shutil
import sys
import termios
import threading
import tty

from . import messages as msg
from .claude import ClaudeSession, Event
from .stt import Recorder, Transcriber
from .textproc import CodeBlock, markdown_to_speech
from .tts import DEFAULT_VOICES, Speaker

DIM, RESET, CYAN = "\033[2m", "\033[0m", "\033[36m"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="speaker",
        description="Lee en voz alta las respuestas de un asistente de IA y permite dictarle por voz.",
        epilog="Ejemplo: speaker --idiomas es,en claude --permission-mode acceptEdits",
    )
    p.add_argument("--idiomas", default="es,en",
                   help=f"idiomas a reconocer al leer, separados por comas; el primero es el "
                        f"principal (disponibles: {','.join(DEFAULT_VOICES)})")
    p.add_argument("--voz", action="append", default=[], metavar="IDIOMA=VOZ",
                   help="voz de Piper para un idioma, p. ej. es=es_MX-ald-medium")
    p.add_argument("--velocidad", type=float, default=1.0, help="velocidad de lectura (0.5 a 2.5)")
    p.add_argument("--modelo-voz", default="small",
                   help="modelo de Whisper para el dictado: tiny, base, small, medium (por defecto small)")
    p.add_argument("--idioma-dictado", default=None,
                   help="fija el idioma del dictado (p. ej. es); por defecto se detecta solo")
    p.add_argument("--sin-confirmar", action="store_true",
                   help="envía el dictado sin pedir confirmación")
    p.add_argument("--decir", metavar="TEXTO", help="lee un texto en voz alta y termina (prueba de voz)")
    p.add_argument("orden", nargs=argparse.REMAINDER,
                   help="programa a envolver y sus argumentos (por ahora solo: claude)")
    return p.parse_args(argv)


class App:
    def __init__(self, args: argparse.Namespace) -> None:
        languages = [l.strip() for l in args.idiomas.split(",") if l.strip()]
        unknown = [l for l in languages if l not in DEFAULT_VOICES]
        voices = dict(v.split("=", 1) for v in args.voz)
        if unknown and not all(l in voices for l in unknown):
            sys.exit(f"speaker: idioma sin voz por defecto: {', '.join(unknown)}. Usa --voz IDIOMA=VOZ")
        self.speaker = Speaker(languages, voices, default_lang=languages[0], speed=args.velocidad)
        self.ui_lang = msg.UI_LANG if msg.UI_LANG in languages else languages[0]
        self.args = args
        self.recorder = Recorder()
        self.transcriber: Transcriber | None = None
        self.session: ClaudeSession | None = None
        self.pending_text: str | None = None  # dictado esperando confirmación
        self.last_response: list[tuple[str, str | None]] = []
        self.last_code: list[CodeBlock] = []
        self._turn_started = False
        self._running = True

    # ---- salida ------------------------------------------------------------
    def announce(self, text: str, detail: str | None = None) -> None:
        line = f"{text} {detail}" if detail else text
        print(f"{DIM}» {line}{RESET}", flush=True)
        self.speaker.say(text, self.ui_lang)
        if detail:
            self.speaker.say(detail)

    def on_event(self, ev: Event) -> None:
        if ev.kind == "text":
            self._start_turn()
            print(ev.text, flush=True)
            spoken = markdown_to_speech(ev.text)
            for i, para in enumerate(spoken.paragraphs):
                lang = self.ui_lang if i in spoken.announcements else None
                self.speaker.say(para, lang)
                self.last_response.append((para, lang))
            if spoken.code_blocks:
                self.last_code = spoken.code_blocks
        elif ev.kind == "tool":
            self._start_turn()
            text, detail = msg.tool_use(ev.tool, ev.args)
            self.announce(text, detail)
        elif ev.kind == "done":
            self._turn_started = False
            if ev.denied:
                self.announce(msg.PERMISSION_DENIED.format(tools=", ".join(ev.denied)))
            self.announce(msg.TURN_ERROR if ev.error else msg.TURN_DONE)
        elif ev.kind == "exit":
            self.announce(msg.AGENT_EXITED.format(agent=self.session.name))
            self._running = False

    def _start_turn(self) -> None:
        if not self._turn_started:
            self._turn_started = True
            self.last_response = []
            self.last_code = []

    def send(self, text: str) -> None:
        self.speaker.stop()
        print(f"{CYAN}Tú: {text}{RESET}", flush=True)
        self.session.send(text)

    # ---- dictado -----------------------------------------------------------
    def toggle_recording(self) -> None:
        if self.recorder.recording:
            audio = self.recorder.stop()
            self.speaker.beep(440)
            if audio is None:
                self.speaker.resume()
                self.announce(msg.NOTHING_HEARD)
                return
            print(f"{DIM}» {msg.TRANSCRIBING}…{RESET}", flush=True)
            threading.Thread(target=self._transcribe, args=(audio,), daemon=True).start()
            return
        if not self.transcriber.ready:
            if self.transcriber.error:
                self.announce(f"Error del reconocimiento de voz: {self.transcriber.error}")
            else:
                self.announce(msg.STT_NOT_READY)
            return
        self.pending_text = None
        self.speaker.pause()
        self.speaker.beep(880)
        print(f"{DIM}» {msg.LISTENING} (espacio para terminar){RESET}", flush=True)
        self.recorder.start()

    def _transcribe(self, audio) -> None:
        text = self.transcriber.transcribe(audio)
        if not text:
            self.speaker.resume()
            self.announce(msg.NOTHING_HEARD)
            return
        if self.args.sin_confirmar:
            self.speaker.resume()
            self.send(text)
            return
        self.pending_text = text
        # Lo pendiente de la respuesta anterior se descarta para leer la confirmación ya.
        self.speaker.stop()
        self.speaker.resume()
        print(f"{DIM}» Entendí:{RESET} {text}", flush=True)
        prefix, rest = msg.HEARD.split("{text}")
        self.speaker.say(prefix.strip(" :"), self.ui_lang)
        self.speaker.say(text)
        self.speaker.say(rest.strip(" ."), self.ui_lang)

    def type_message(self, fd: int, old_attrs) -> None:
        self.speaker.stop()
        self.speaker.say(msg.TYPE_PROMPT, self.ui_lang)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        try:
            text = input(msg.TYPE_PROMPT).strip()
        except EOFError:
            text = ""
        finally:
            tty.setcbreak(fd)
        if text:
            self.send(text)
        else:
            self.announce(msg.CANCELLED)

    # ---- teclado -----------------------------------------------------------
    def handle_key(self, key: str, fd: int, old_attrs) -> None:
        if key == " ":
            self.toggle_recording()
        elif key in ("\n", "\r"):
            if self.pending_text:
                text, self.pending_text = self.pending_text, None
                self.send(text)
            else:
                self.announce(msg.NOTHING_TO_SEND)
        elif key == "\x1b":
            if self.recorder.recording:
                self.recorder.stop()
                self.speaker.beep(440)
                self.speaker.resume()
                self.announce(msg.CANCELLED)
            elif self.pending_text:
                self.pending_text = None
                self.speaker.stop()
                self.announce(msg.CANCELLED)
            else:
                self.speaker.stop()
                self.speaker.resume()
        elif key in "eE":
            self.type_message(fd, old_attrs)
        elif key in "rR":
            self.speaker.stop()
            if not self.last_response:
                self.announce(msg.NOTHING_TO_REPEAT)
            for para, lang in self.last_response:
                self.speaker.say(para, lang)
        elif key in "cC":
            self.speaker.stop()
            if not self.last_code:
                self.announce(msg.NO_CODE)
            for block in self.last_code:
                for line in block.lines:
                    if line.strip():
                        self.speaker.say(line.strip())
        elif key in "+-":
            value = self.speaker.change_speed(0.1 if key == "+" else -0.1)
            self.announce(msg.SPEED.format(value=str(value).replace(".", ",")))
        elif key in "hH?":
            self.speaker.stop()
            self.announce(msg.HELP)
        elif key in "qQ":
            self._running = False

    def run(self, command: list[str]) -> int:
        print(f"{DIM}» {msg.LOADING_VOICES}…{RESET}", flush=True)
        self.speaker.prepare()
        self.transcriber = Transcriber(self.args.modelo_voz, self.args.idioma_dictado)
        self.session = ClaudeSession(command[0], command[1:], self.on_event)
        self.announce(msg.READY)

        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        try:
            while self._running:
                ready, _, _ = select.select([fd], [], [], 0.2)
                if not ready:
                    continue
                key = os.read(fd, 1).decode(errors="ignore")
                if key == "\x1b":
                    # Las flechas y otras teclas especiales envían secuencias que empiezan
                    # con Escape: se descartan para no confundirlas con la tecla Escape.
                    if select.select([fd], [], [], 0.05)[0]:
                        os.read(fd, 16)
                        continue
                self.handle_key(key, fd, old_attrs)
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            if self.recorder.recording:
                self.recorder.stop()
            self.session.close()
            self.speaker.stop()
            print(msg.GOODBYE)
        return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    app = App(args)
    if args.decir:
        app.speaker.prepare()
        app.speaker.say(args.decir)
        while app.speaker.busy:
            threading.Event().wait(0.1)
        return 0
    if not args.orden:
        sys.exit("speaker: indica el programa a envolver, por ejemplo: speaker claude")
    program = os.path.basename(args.orden[0])
    if program != "claude":
        sys.exit(f"speaker: por ahora solo se admite 'claude' (recibido: {program})")
    if not shutil.which(args.orden[0]):
        sys.exit(f"speaker: no se encontró el programa {args.orden[0]}")
    if not sys.stdin.isatty():
        sys.exit("speaker: necesita ejecutarse en una terminal interactiva")
    return app.run(args.orden)


if __name__ == "__main__":
    sys.exit(main())
