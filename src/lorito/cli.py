"""Punto de entrada: `lorito [opciones] claude [argumentos de claude...]`."""

from __future__ import annotations

import argparse
import os
import select
import shutil
import sys
import termios
import threading
import tty

from . import __version__, full_version
from . import messages as msg
from . import permissions
from .questions import TOOL_NAME as ASK_TOOL, QuestionFlow, match_options
from .claude import ClaudeSession, Event
from .stt import Recorder, Transcriber
from .textproc import CodeBlock, markdown_to_speech
from .tts import DEFAULT_VOICES, Speaker

TOOL_ANNOUNCE_DELAY = 0.4  # segundos

DIM, RESET, CYAN, BOLD = "\033[2m", "\033[0m", "\033[36m", "\033[1m"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="lorito",
        description="Lee en voz alta las respuestas de un asistente de IA y permite dictarle por voz.",
        epilog="Ejemplo: lorito --idiomas es,en claude --permission-mode acceptEdits",
    )
    p.add_argument("-V", "--version", action="version", version=f"lorito {full_version()}")
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
            sys.exit(f"lorito: idioma sin voz por defecto: {', '.join(unknown)}. Usa --voz IDIOMA=VOZ")
        self.speaker = Speaker(languages, voices, default_lang=languages[0], speed=args.velocidad)
        self.ui_lang = msg.UI_LANG if msg.UI_LANG in languages else languages[0]
        self.args = args
        self.recorder = Recorder()
        self.transcriber: Transcriber | None = None
        self.session: ClaudeSession | None = None
        self.pending_text: str | None = None  # dictado esperando confirmación con Enter
        # Qué es el texto pendiente: "message" (mensaje normal), "feedback" (indicación al
        # rechazar un permiso) o "answer" (respuesta libre a una pregunta con opciones).
        self.pending_kind = "message"
        self.question: QuestionFlow | None = None  # pregunta con opciones en curso
        # Peticiones de permiso y preguntas en espera; la primera es la actual.
        self.permissions: list[Event] = []
        self._user_stopped = False  # el usuario rechazó un permiso en este turno
        self._feedback_after_turn: str | None = None
        self._tool_timers: dict[str, threading.Timer] = {}
        # (párrafo, idioma fijo o None, idioma del mensaje como respaldo)
        self.last_response: list[tuple[str, str | None, str]] = []
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
            # Idioma del mensaje completo: respaldo para los fragmentos cortos (números de
            # lista, títulos) que no bastan para detectar el idioma por sí solos.
            message_lang = self.speaker.detect(" ".join(
                p for i, p in enumerate(spoken.paragraphs) if i not in spoken.announcements))
            for i, para in enumerate(spoken.paragraphs):
                lang = self.ui_lang if i in spoken.announcements else None
                self.speaker.say(para, lang, message_lang)
                self.last_response.append((para, lang, message_lang))
            if spoken.code_blocks:
                self.last_code = spoken.code_blocks
        elif ev.kind == "tool":
            self._start_turn()
            # Si la herramienta necesita permiso, la petición llega justo después: se espera
            # un instante para no anunciar "Ejecutando..." algo que quizá se rechace.
            timer = threading.Timer(TOOL_ANNOUNCE_DELAY, self._announce_tool, args=(ev,))
            self._tool_timers[ev.tool_use_id] = timer
            timer.start()
        elif ev.kind == "permission":
            timer = self._tool_timers.pop(ev.tool_use_id, None)
            if timer:
                timer.cancel()
            self.permissions.append(ev)
            if len(self.permissions) == 1:
                self.ask_permission()
        elif ev.kind == "permission_cancel":
            current = self.permissions[0] if self.permissions else None
            self.permissions = [p for p in self.permissions if p.request_id != ev.request_id]
            if current and current.request_id == ev.request_id:
                self.announce(msg.PERMISSION_CANCELLED)
                if self.permissions:
                    self.ask_permission()
        elif ev.kind == "done":
            self._turn_started = False
            self.permissions.clear()
            self.question = None
            if self._user_stopped:
                self._user_stopped = False
                feedback, self._feedback_after_turn = self._feedback_after_turn, None
                if feedback:
                    self.send(feedback, stop_speech=False)
                else:
                    self.announce(msg.TURN_STOPPED)
                return
            if ev.denied:
                self.announce(msg.PERMISSION_DENIED.format(tools=", ".join(ev.denied)))
            self.announce(msg.TURN_ERROR if ev.error else msg.TURN_DONE)
        elif ev.kind == "exit":
            self.announce(msg.AGENT_EXITED.format(agent=self.session.name))
            self._running = False

    def _announce_tool(self, ev: Event) -> None:
        if self._tool_timers.pop(ev.tool_use_id, None):
            text, detail = msg.tool_use(ev.tool, ev.args)
            self.announce(text, detail)

    def _start_turn(self) -> None:
        if not self._turn_started:
            self._turn_started = True
            self.last_response = []
            self.last_code = []

    def send(self, text: str, stop_speech: bool = True) -> None:
        if stop_speech:
            self.speaker.stop()
        print(f"{CYAN}Tú: {text}{RESET}", flush=True)
        self.session.send(text)

    # ---- permisos ----------------------------------------------------------
    def ask_permission(self) -> None:
        ev = self.permissions[0]
        if ev.tool == ASK_TOOL:
            if self.question is None or self.question.request is not ev:
                self.question = QuestionFlow(ev)
            self.present_question()
            return
        question, description, _ = msg.permission_request(ev.tool, ev.args, ev.text)
        print(f"{BOLD}{CYAN}? {question}{' ' + description if description else ''}{RESET}", flush=True)
        if ev.tool == "Bash" and ev.args.get("command"):
            print(f"{CYAN}  $ {ev.args['command']}{RESET}", flush=True)
        print(f"{DIM}  [S] permitir  [N] rechazar  [T] siempre  [D] detalle  [Espacio] voz{RESET}",
              flush=True)
        self.speaker.beep(660, 90)
        self.speaker.say(question, self.ui_lang)
        if description:
            self.speaker.say(description)
        if len(self.permissions) > 1:
            self.speaker.say(msg.PERMISSION_MORE.format(n=len(self.permissions) - 1), self.ui_lang)
        self.speaker.say(msg.PERMISSION_OPTIONS, self.ui_lang)

    def permission_detail(self) -> None:
        _, _, detail = msg.permission_request(self.permissions[0].tool, self.permissions[0].args,
                                              self.permissions[0].text)
        self.speaker.stop()
        self.speaker.say(detail or msg.NO_PERMISSION_PENDING, self.ui_lang)

    def resolve_permission(self, decision: str, feedback: str | None = None) -> None:
        if not self.permissions:
            # La petición ya no existe (Claude la retiró): la indicación va como mensaje normal.
            if feedback:
                self.send(feedback)
            else:
                self.announce(msg.NO_PERMISSION_PENDING)
            return
        ev = self.permissions.pop(0)
        self.speaker.stop()
        if decision in (permissions.ALLOW, permissions.ALWAYS):
            self.session.allow(ev, always=decision == permissions.ALWAYS)
            self.announce(msg.PERMISSION_ALWAYS if decision == permissions.ALWAYS
                          else msg.PERMISSION_ALLOWED)
            if self.permissions:
                self.ask_permission()
            return
        # Rechazo: Claude detiene el turno. Las indicaciones del usuario se envían como un
        # mensaje normal al terminar el turno; si fueran dentro del rechazo, Claude las
        # trataría como texto no fiable de una herramienta.
        self.session.deny(ev)
        self.permissions.clear()
        was_question, self.question = self.question is not None, None
        self._user_stopped = True
        self._feedback_after_turn = feedback
        if feedback:
            self.announce(msg.PERMISSION_FEEDBACK)
        else:
            self.announce(msg.QUESTION_DECLINED if was_question else msg.PERMISSION_DENIED_BY_USER)

    def answer_permission_text(self, text: str, confirm: bool = True) -> None:
        """Respuesta hablada o escrita a la petición de permiso actual. `confirm` pide
        Enter antes de enviar una indicación libre (para el dictado, que puede fallar)."""
        decision = permissions.classify(text)
        if decision != permissions.FEEDBACK or not confirm:
            self.resolve_permission(decision, text if decision == permissions.FEEDBACK else None)
            return
        self.confirm_text(text, "feedback", msg.HEARD_FEEDBACK)

    def confirm_text(self, text: str, kind: str, template: str) -> None:
        """Lee lo que se entendió y deja el texto pendiente hasta que se pulse Enter."""
        self.pending_text, self.pending_kind = text, kind
        self.speaker.stop()
        print(f"{DIM}» Entendí:{RESET} {text}", flush=True)
        prefix, rest = template.split("{text}")
        self.speaker.say(prefix.strip(" :"), self.ui_lang)
        self.speaker.say(text)
        self.speaker.say(rest.strip(" ."), self.ui_lang)

    # ---- preguntas con opciones ---------------------------------------------
    @property
    def question_active(self) -> bool:
        return bool(self.permissions) and self.permissions[0].tool == ASK_TOOL \
            and self.question is not None

    def present_question(self) -> None:
        q = self.question
        total = len(q.questions)
        intro = (msg.QUESTION_INTRO if total == 1
                 else msg.QUESTION_INTRO_N.format(i=q.index + 1, n=total))
        text = q.current.get("question", "")
        header = q.current.get("header")
        print(f"{BOLD}{CYAN}? {intro}{RESET} {f'[{header}] ' if header else ''}{BOLD}{text}{RESET}",
              flush=True)
        self.speaker.beep(660, 90)
        self.speaker.say(intro, self.ui_lang)
        self.speaker.say(text)
        for n, option in enumerate(q.current.get("options") or [], start=1):
            label, description = option.get("label", ""), option.get("description", "")
            mark = "[x] " if n - 1 in q.selected else ("[ ] " if q.multi else "")
            print(f"  {CYAN}{n}.{RESET} {mark}{label}{DIM}{' — ' + description if description else ''}{RESET}",
                  flush=True)
            self.speaker.say(msg.OPTION.format(n=n, label=label), self.ui_lang)
            if description:
                self.speaker.say(description)
        hint = "[1-9] marcar  [Enter] confirmar" if q.multi else "[1-9] elegir"
        print(f"{DIM}  {hint}  [Espacio/E] voz o texto  [P] repetir  [N] no responder{RESET}",
              flush=True)
        self.speaker.say(msg.QUESTION_HELP_MULTI if q.multi else msg.QUESTION_HELP_SINGLE,
                         self.ui_lang)

    def choose_options(self, indices: list[int]) -> None:
        """Responde la pregunta actual con esas opciones y pasa a la siguiente."""
        q = self.question
        labels = ", ".join(q.labels[i] for i in sorted(indices))
        self.speaker.stop()
        self.announce(msg.OPTION_CHOSEN.format(labels=labels))
        self._advance(q.answer_options(indices))

    def answer_question_free(self, text: str) -> None:
        self.speaker.stop()
        self.announce(msg.OPTION_CHOSEN.format(labels=text))
        self._advance(self.question.answer(text))

    def _advance(self, finished: bool) -> None:
        if not finished:
            self.present_question()
            return
        q, self.question = self.question, None
        ev = self.permissions.pop(0)
        self.session.allow(ev, updated_input=q.updated_input())
        self.announce(msg.ANSWERS_SENT)
        if self.permissions:
            self.ask_permission()

    def answer_question_text(self, text: str, confirm: bool = True) -> None:
        """Respuesta hablada o escrita: número, nombre de opción o texto libre."""
        q = self.question
        found = match_options(text, q.labels)
        if found and (q.multi or len(found) == 1):
            self.choose_options(found)
        elif not confirm:
            self.answer_question_free(text)
        else:
            self.confirm_text(text, "answer", msg.HEARD_ANSWER)

    def handle_question_key(self, key: str) -> bool:
        """Teclas de la pregunta en curso. Devuelve False si la tecla no es suya."""
        q = self.question
        lower = key.lower()
        if key.isdigit() and key != "0":
            n = int(key)
            if n > len(q.labels):
                self.speaker.stop()
                self.announce(msg.NO_SUCH_OPTION.format(n=n))
            elif q.multi:
                marked = q.toggle(n - 1)
                self.speaker.stop()
                label = q.labels[n - 1]
                self.announce((msg.OPTION_MARKED if marked else msg.OPTION_UNMARKED).format(label=label))
            else:
                self.choose_options([n - 1])
            return True
        if key in ("\n", "\r") and not self.pending_text:
            if not q.multi:
                self.announce(msg.QUESTION_HOW)
            elif not q.selected:
                self.announce(msg.NONE_MARKED)
            else:
                self.choose_options(list(q.selected))
            return True
        if lower == "n":
            self.resolve_permission(permissions.DENY)
            return True
        if lower == "p":
            self.speaker.stop()
            self.present_question()
            return True
        if lower in "std":
            self.speaker.stop()
            self.announce(msg.QUESTION_HOW)
            return True
        return False

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
        self.pending_text, self.pending_kind = None, "message"
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
        self.speaker.resume()
        self.handle_text(text, confirm=not self.args.sin_confirmar)

    def handle_text(self, text: str, confirm: bool) -> None:
        """Texto dictado o escrito: responde a la pregunta o permiso en curso, o es un mensaje."""
        if self.question_active:
            self.answer_question_text(text, confirm)
        elif self.permissions:
            self.answer_permission_text(text, confirm)
        elif confirm:
            # Lo pendiente de la respuesta anterior se descarta para leer la confirmación ya.
            self.confirm_text(text, "message", msg.HEARD)
        else:
            self.send(text)

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
        if not text:
            self.announce(msg.CANCELLED)
        else:
            self.handle_text(text, confirm=False)

    # ---- teclado -----------------------------------------------------------
    def handle_key(self, key: str, fd: int, old_attrs) -> None:
        lower = key.lower()
        if self.question_active and self.handle_question_key(key):
            return
        if lower in "sntdp" and key.strip():
            if not self.permissions:
                self.announce(msg.NO_PERMISSION_PENDING)
            elif lower == "s":
                self.resolve_permission(permissions.ALLOW)
            elif lower == "t":
                self.resolve_permission(permissions.ALWAYS)
            elif lower == "n":
                self.resolve_permission(permissions.DENY)
            elif lower == "d":
                self.permission_detail()
            else:
                self.speaker.stop()
                self.ask_permission()
        elif key == " ":
            self.toggle_recording()
        elif key in ("\n", "\r"):
            if self.pending_text:
                text, kind = self.pending_text, self.pending_kind
                self.pending_text, self.pending_kind = None, "message"
                if kind == "feedback":
                    self.resolve_permission(permissions.FEEDBACK, text)
                elif kind == "answer" and self.question_active:
                    self.answer_question_free(text)
                else:
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
                self.pending_text, self.pending_kind = None, "message"
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
            for para, lang, fallback in self.last_response:
                self.speaker.say(para, lang, fallback)
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
            print_keys()
            self.speaker.say(msg.HELP, self.ui_lang)
        elif key in "qQ":
            self._running = False

    @staticmethod
    def session_name(command: list[str]) -> str:
        return ClaudeSession.name

    def run(self, command: list[str]) -> int:
        print_welcome(self.session_name(command))
        print(f"{DIM}» {msg.LOADING_VOICES}…{RESET}", flush=True)
        self.speaker.prepare()
        self.transcriber = Transcriber(self.args.modelo_voz, self.args.idioma_dictado)
        self.session = ClaudeSession(command[0], command[1:], self.on_event)
        print(f"{DIM}» {msg.READY.format(version=__version__)}{RESET}", flush=True)
        self.speaker.say(msg.READY.format(version=__version__.replace(".", " punto ")), self.ui_lang)

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


def print_keys() -> None:
    sections = ((msg.KEYS_TITLE, msg.KEYS), (msg.PERMISSION_KEYS_TITLE, msg.PERMISSION_KEYS),
                (msg.QUESTION_KEYS_TITLE, msg.QUESTION_KEYS))
    width = max(len(k) for _, keys in sections for k, _, _ in keys)
    for title, keys in sections:
        print(f"{BOLD}{title}{RESET}")
        for key, _, action in keys:
            print(f"  {CYAN}{key.ljust(width)}{RESET}  {action[0].upper()}{action[1:]}")
        print(flush=True)


def print_welcome(agent: str) -> None:
    title = msg.WELCOME_TITLE.format(version=full_version())
    subtitle = msg.WELCOME_SUBTITLE.format(agent=agent)
    width = max(len(title), len(subtitle)) + 4
    print(f"╭{'─' * width}╮")
    print(f"│  {BOLD}{title.ljust(width - 2)}{RESET}│")
    print(f"│  {subtitle.ljust(width - 2)}│")
    print(f"╰{'─' * width}╯\n")
    print_keys()


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
        sys.exit("lorito: indica el programa a envolver, por ejemplo: lorito claude")
    program = os.path.basename(args.orden[0])
    if program != "claude":
        sys.exit(f"lorito: por ahora solo se admite 'claude' (recibido: {program})")
    if not shutil.which(args.orden[0]):
        sys.exit(f"lorito: no se encontró el programa {args.orden[0]}")
    if not sys.stdin.isatty():
        sys.exit("lorito: necesita ejecutarse en una terminal interactiva")
    return app.run(args.orden)


if __name__ == "__main__":
    sys.exit(main())
