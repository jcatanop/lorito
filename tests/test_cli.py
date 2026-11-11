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
    app.handle_key("s", None, None)
    assert app.session.calls == [f"allow:{msg.PLAN_TOOL}"]
    assert app.speaker.said[-1] == msg.PLAN_APPROVED


def test_plan_detail_rereads_plan_and_repeat_key_has_it(app):
    app.send("Planea crear nota.txt")
    app.on_event(plan_request())
    app.speaker.said.clear()
    app.handle_key("d", None, None)
    assert "Crear nota.txt con el texto hola." in " ".join(app.speaker.said)
    assert any("Crear nota.txt" in para for para, _, _ in app.last_response)


def test_rejecting_plan_stops_claude(app):
    app.send("Planea crear nota.txt")
    app.on_event(plan_request())
    app.handle_key("n", None, None)
    assert app.session.calls == [f"deny:{msg.PLAN_TOOL}"]
