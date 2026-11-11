"""Lectura del portapapeles con programas del sistema simulados."""

import pytest

from lorito import clipboard
from lorito.clipboard import ClipboardError, read_clipboard


def fake_tool(tmp_path, name, script):
    path = tmp_path / name
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(0o755)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    return tmp_path


def test_reads_with_wl_paste(env):
    fake_tool(env, "wl-paste", "printf 'Traceback\\nError: ñ'")
    assert read_clipboard() == "Traceback\nError: ñ"


def test_missing_tool_explains_what_to_install(env):
    with pytest.raises(ClipboardError, match="wl-clipboard"):
        read_clipboard()


def test_empty_clipboard(env):
    fake_tool(env, "wl-paste", "echo 'Nothing is copied' >&2; exit 1")
    with pytest.raises(ClipboardError) as exc:
        read_clipboard()
    assert str(exc.value) == clipboard.EMPTY


def test_x11_fallback(env, monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY")
    monkeypatch.setenv("DISPLAY", ":0")
    fake_tool(env, "xclip", "printf 'desde X11'")
    assert read_clipboard() == "desde X11"
