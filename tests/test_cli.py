"""Comportamiento de la aplicación ante los eventos de Claude, con voz y Claude simulados."""

import pytest

from lorito import messages as msg
from lorito.claude import Event
from lorito.cli import App, parse_args


class FakeSpeaker:
    def __init__(self):
        self.said: list[str] = []
        self.beeps = 0
        self.busy = False

    def say(self, text, lang=None, fallback=None):
        self.said.append(text)

    def beep(self, *args, **kwargs):
        self.beeps += 1

    def detect(self, text):
        return "es"

    def stop(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass


class FakeSession:
    name = "Claude"

    def __init__(self):
        self.sent: list[str] = []
        self.calls: list[str] = []

    def send(self, text):
        self.sent.append(text)

    def interrupt(self):
        self.calls.append("interrupt")

    def allow(self, ev, always=False, updated_input=None):
        self.calls.append(f"allow:{ev.tool}")

    def deny(self, ev):
        self.calls.append(f"deny:{ev.tool}")


@pytest.fixture
def app():
    a = App(parse_args(["claude"]))
    a.speaker = FakeSpeaker()
    a.session = FakeSession()
    return a


def test_interrupt_stops_turn_and_ignores_late_output(app):
    app.send("Escribe una lista larga")
    app.interrupt()
    assert app.session.calls == ["interrupt"]
    app.on_event(Event("text", text="1. Texto a medio escribir"))
    app.on_event(Event("permission", tool="Bash", request_id="r1"))
    app.on_event(Event("done", error=True, subtype="error_during_execution"))
    assert "1. Texto a medio escribir" not in app.speaker.said
    assert app.session.calls == ["interrupt", "deny:Bash"]
    assert app.speaker.said[-1] == msg.INTERRUPTED
    assert msg.TURN_ERROR not in app.speaker.said
    assert not app.working


def test_interrupt_when_idle_does_nothing(app):
    app.interrupt()
    assert app.session.calls == []
    assert app.speaker.said == [msg.NOT_WORKING]


def test_turn_started_by_claude_counts_as_working(app):
    app.on_event(Event("text", text="Terminó la tarea en segundo plano."))
    assert app.working
    app.on_event(Event("done"))
    assert not app.working


def test_api_error_is_announced_and_not_repeated_at_the_end(app):
    app.send("hola")
    reason = "There's an issue with the selected model (x). It may not exist."
    app.on_event(Event("text", text=reason, error=True, subtype="model_not_found"))
    app.on_event(Event("done", error=True, text=reason, subtype="success"))
    assert app.speaker.said[0] == msg.CLAUDE_ERROR
    assert app.speaker.said.count(reason) == 1
    assert app.speaker.said[-1] == msg.TURN_ERROR


def test_error_result_reads_its_reason(app):
    app.send("hola")
    app.on_event(Event("done", error=True, text="Credit balance is too low", subtype="success"))
    assert app.speaker.said[-2:] == [msg.TURN_ERROR_REASON, "Credit balance is too low"]


def test_error_without_reason_uses_its_type(app):
    app.send("hola")
    app.on_event(Event("done", error=True, subtype="error_max_turns"))
    assert app.speaker.said[-1] == msg.ERROR_SUBTYPES["error_max_turns"]


def test_exit_with_error_reads_last_message(app):
    app.on_event(Event("exit", error=True, subtype="1",
                       text="cargando...\nInvalid API key · Please run /login"))
    assert app.speaker.said[-1] == "Invalid API key · Please run /login"
    assert not app._running


def test_exit_skips_internal_diagnostic_lines(app):
    app.on_event(Event("exit", error=True, subtype="1",
                       text='Not logged in\n[claude-code:auth] {"query_source":"sdk"}'))
    assert app.speaker.said[-1] == "Not logged in"
    app.on_event(Event("exit", error=True, subtype="1", text='[claude-code:x] {"a":1}'))
    assert app.speaker.said[-1] == msg.AGENT_EXITED_ERROR.format(agent="Claude", code="1")


def test_waiting_tick_while_claude_works_in_silence(app):
    app.send("Revisa el proyecto")
    start = app._last_activity
    app.tick(start + 5)
    assert app.speaker.beeps == 0  # aún no pasó el intervalo
    for i in range(1, 6):
        app.tick(start + 8 * i)
    assert app.speaker.beeps == 5 and app.speaker.said == []
    app.tick(start + 48)  # el sexto aviso se dice en voz alta
    assert app.speaker.said == [msg.STILL_WORKING]


def test_no_waiting_tick_when_idle_speaking_or_asking(app):
    t = app._last_activity
    app.tick(t + 100)  # Claude no trabaja
    app.send("hola")
    app.speaker.busy = True
    app.tick(t + 200)  # se está leyendo algo
    app.speaker.busy = False
    app.permissions.append(Event("permission", tool="Bash"))
    app.tick(t + 300)  # se espera la respuesta del usuario
    assert app.speaker.beeps == 0


def test_waiting_tick_can_be_disabled():
    a = App(parse_args(["--aviso-trabajo", "0", "claude"]))
    a.speaker, a.session = FakeSpeaker(), FakeSession()
    a.send("hola")
    a.tick(a._last_activity + 1000)
    assert a.speaker.beeps == 0


PLAN = "# Plan: crear nota.txt\n\n## Pasos\n1. Crear `nota.txt` con el texto hola.\n"


def plan_request():
    return Event("permission", tool=msg.PLAN_TOOL, request_id="p1", tool_use_id="t1",
                 args={"plan": PLAN, "planFilePath": "/tmp/plan.md"})


def test_plan_is_read_before_approval(app):
    app.send("Planea crear nota.txt")
    app.on_event(plan_request())
    said = " ".join(app.speaker.said)
    assert "pide tu aprobación" in said
    assert "Crear nota.txt con el texto hola." in said
    assert app.speaker.said[-1] == msg.PLAN_OPTIONS
    app.handle_key("s")
    assert app.session.calls == [f"allow:{msg.PLAN_TOOL}"]
    assert app.speaker.said[-1] == msg.PLAN_APPROVED


def test_plan_detail_rereads_plan_and_repeat_key_has_it(app):
    app.send("Planea crear nota.txt")
    app.on_event(plan_request())
    app.speaker.said.clear()
    app.handle_key("d")
    assert "Crear nota.txt con el texto hola." in " ".join(app.speaker.said)
    assert any("Crear nota.txt" in para for para, _, _ in app.last_response)


def test_rejecting_plan_stops_claude(app):
    app.send("Planea crear nota.txt")
    app.on_event(plan_request())
    app.handle_key("n")
    assert app.session.calls == [f"deny:{msg.PLAN_TOOL}"]


def type_keys(app, text):
    for ch in text:
        app.handle_key(ch)


def test_typed_message_with_pasted_multiline_text(app, capsys):
    app.handle_key("e")
    type_keys(app, "Mira este error: ")
    app.handle_paste("Traceback:\n  línea 12\nquit()")
    type_keys(app, "x\x7f")  # una letra y su borrado
    app.handle_key("\n")
    # Lo pegado de varias líneas se adjunta aparte, no dentro de la línea del mensaje.
    assert app.session.sent == ["Mira este error:\n\n```\nTraceback:\n  línea 12\nquit()\n```"]
    assert app.typing is None


def test_short_paste_while_typing_goes_inline_at_cursor(app):
    app.handle_key("e")
    type_keys(app, "abre  y dime")
    for _ in range(len(" y dime")):
        app.handle_key("left")
    app.handle_paste("config.toml")
    app.handle_key("\n")
    assert app.session.sent == ["abre config.toml y dime"]


def test_arrows_outside_typing_do_nothing(app):
    app.handle_key("left")
    app.handle_key("delete")
    assert app.speaker.said == [] and app.session.calls == []


def test_letters_while_typing_are_not_commands(app):
    app.send("hola")
    app.on_event(Event("permission", tool="Bash", request_id="r1"))
    app.handle_key("E")
    type_keys(app, "sin prisa")  # contiene s, n, i, p...
    assert app.session.calls == []
    app.handle_key("\x1b")
    assert app.typing is None and app.speaker.said[-1] == msg.CANCELLED


def test_paste_outside_typing_is_not_taken_as_keys(app):
    app.send("hola")
    app.on_event(Event("permission", tool="Bash", request_id="r1"))
    app.handle_paste("s\nq\ni")
    assert app.session.calls == [] and app._running
    assert app.attachments == ["s\nq\ni"]


ERROR = 'Traceback (most recent call last):\n  File "app.py", line 12\nValueError: ```'


def test_clipboard_attachment_goes_with_dictated_message(app, monkeypatch):
    monkeypatch.setattr("lorito.cli.read_clipboard", lambda: ERROR + "\n")
    app.handle_key("v")
    said = " ".join(app.speaker.said)
    assert "3 líneas" in said and "Traceback (most recent call last):" in said
    assert ERROR not in app.speaker.said  # no se lee entero
    app.confirm_text("Me sale este error", "message", msg.HEARD)
    assert "Con un texto adjunto." in app.speaker.said
    app.handle_key("\n")
    assert app.session.sent == ["Me sale este error\n\n````\n" + ERROR + "\n````"]
    assert app.attachments == []


def test_attachment_alone_is_sent_with_enter(app):
    app.handle_paste("línea 1\nlínea 2")
    app.handle_key("\n")
    assert app.session.sent == ["```\nlínea 1\nlínea 2\n```"]


def test_detail_key_reads_attachment_and_escape_removes_it(app):
    app.handle_paste("primera\n\nsegunda")
    app.speaker.said.clear()
    app.handle_key("d")
    assert app.speaker.said == ["primera", "segunda"]
    app.handle_key("\x1b")
    assert app.attachments == [] and app.speaker.said[-1] == msg.ATTACHMENTS_REMOVED


def test_cancelling_dictation_keeps_attachment(app):
    app.handle_paste("error")
    app.confirm_text("mira esto", "message", msg.HEARD)
    app.handle_key("\x1b")
    assert app.attachments == ["error"]
    assert app.speaker.said[-1] == msg.CANCELLED_KEEP_ATTACHMENTS


def test_clipboard_problem_is_spoken(app, monkeypatch):
    from lorito.clipboard import NO_TOOL, ClipboardError

    def fail():
        raise ClipboardError(NO_TOOL)
    monkeypatch.setattr("lorito.cli.read_clipboard", fail)
    app.handle_key("v")
    assert app.speaker.said[-1] == NO_TOOL and app.attachments == []


def test_feedback_after_rejection_carries_attachment(app):
    app.send("arregla el error")
    app.on_event(Event("permission", tool="Bash", request_id="r1"))
    app.handle_paste("log de error")
    app.resolve_permission("feedback", "usa este registro")
    app.on_event(Event("done"))
    assert app.session.sent[-1] == "usa este registro\n\n```\nlog de error\n```"


def test_claude_events_wait_while_a_key_is_being_handled(app):
    import threading
    app.send("hola")
    app._lock.acquire()  # como el bucle del teclado mientras atiende una tecla
    t = threading.Thread(target=app.on_event,
                         args=(Event("permission", tool="Bash", request_id="r1"),))
    t.start()
    t.join(0.2)
    assert t.is_alive() and app.permissions == []  # espera su turno
    app._lock.release()
    t.join(1)
    assert [p.request_id for p in app.permissions] == ["r1"]


def test_transcription_result_waits_for_the_lock(app):
    import threading
    app.transcriber = type("T", (), {"transcribe": lambda self, audio: "hola"})()
    app._lock.acquire()
    t = threading.Thread(target=app._transcribe, args=(None,))
    t.start()
    t.join(0.2)
    assert t.is_alive() and app.pending_text is None
    app._lock.release()
    t.join(1)
    assert app.pending_text == "hola"


def test_quit_when_idle_is_immediate(app):
    app.handle_key("q")
    assert not app._running


def test_quit_while_working_asks_first(app):
    app.send("revisa el proyecto")
    app.handle_key("q")
    assert app._running and app.speaker.said[-1] == msg.QUIT_CONFIRM
    app.handle_key("Q")
    assert not app._running


def test_other_key_or_timeout_cancels_quit(app, monkeypatch):
    import lorito.cli as cli
    app.send("revisa el proyecto")
    app.handle_key("q")
    app.handle_key("r")  # otra tecla: se sigue
    app.handle_key("q")
    assert app._running  # vuelve a preguntar
    now = app._quit_armed_at
    monkeypatch.setattr(cli.time, "monotonic", lambda: now + cli.QUIT_CONFIRM_SECONDS + 1)
    app.handle_key("q")
    assert app._running  # pasó el plazo: vuelve a preguntar


def test_version_warning(app, tmp_path, monkeypatch, capsys):
    import lorito.cli as cli
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "installed_version", lambda exe: cli.TESTED_VERSION)
    app.check_claude_version("claude")
    assert app.speaker.said == []  # versión probada: solo en pantalla
    monkeypatch.setattr(cli, "installed_version", lambda exe: "9.9.9")
    app.check_claude_version("claude")
    assert "9 punto 9 punto 9" in app.speaker.said[-1]
    app.speaker.said.clear()
    app.check_claude_version("claude")
    assert app.speaker.said == []  # ya avisada: solo en pantalla
    assert "9.9.9" in capsys.readouterr().out
