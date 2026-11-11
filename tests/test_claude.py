"""Interpretación de los mensajes de Claude Code en modo stream-json."""

from lorito.claude import _parse


def test_api_error_marks_text_event():
    [ev] = _parse({"type": "assistant", "error": "model_not_found", "message": {
        "content": [{"type": "text", "text": "There's an issue with the selected model."}]}})
    assert ev.kind == "text" and ev.error and ev.subtype == "model_not_found"


def test_normal_text_is_not_an_error():
    [ev] = _parse({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hola"}]}})
    assert not ev.error and ev.subtype == ""


def test_error_result_carries_reason_and_type():
    [ev] = _parse({"type": "result", "subtype": "success", "is_error": True,
                   "result": "Credit balance is too low"})
    assert ev.kind == "done" and ev.error and ev.text == "Credit balance is too low"


def test_interrupted_result_has_no_reason():
    [ev] = _parse({"type": "result", "subtype": "error_during_execution", "is_error": True,
                   "result": None, "errors": ["[ede_diagnostic] result_type=user"]})
    assert ev.error and ev.text == "" and ev.subtype == "error_during_execution"


def test_successful_result_does_not_repeat_the_answer():
    [ev] = _parse({"type": "result", "subtype": "success", "is_error": False, "result": "Hola"})
    assert not ev.error and ev.text == ""


def fake_claude(tmp_path, output):
    path = tmp_path / "claude"
    path.write_text(f"#!/bin/sh\necho '{output}'\n")
    path.chmod(0o755)
    return str(path)


def test_installed_version(tmp_path):
    from lorito.claude import installed_version
    assert installed_version(fake_claude(tmp_path, "2.1.322 (Claude Code)")) == "2.1.322"
    assert installed_version(fake_claude(tmp_path, "algo raro")) is None
    assert installed_version(str(tmp_path / "no-existe")) is None


def test_untested_version_is_spoken_only_once(tmp_path, monkeypatch):
    from lorito.claude import first_warning_for
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert first_warning_for("2.2.0")
    assert not first_warning_for("2.2.0")
    assert first_warning_for("2.2.1")
