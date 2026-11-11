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
