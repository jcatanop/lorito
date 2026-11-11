"""Lectura del portapapeles del sistema con wl-paste (Wayland), xclip o xsel (X11)."""

from __future__ import annotations

import os
import shutil
import subprocess


class ClipboardError(Exception):
    """El portapapeles no se pudo leer; el mensaje explica por qué, para leerlo en voz alta."""


NO_TOOL = ("No puedo leer el portapapeles: falta un programa del sistema. "
           "Instala wl-clipboard si usas Wayland, o xclip si usas X11.")
EMPTY = "El portapapeles está vacío o no contiene texto."


def _commands() -> list[list[str]]:
    commands = []
    if os.environ.get("WAYLAND_DISPLAY"):
        commands.append(["wl-paste", "--no-newline", "--type", "text"])
    if os.environ.get("DISPLAY"):
        commands += [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]
    return commands


def read_clipboard() -> str:
    available = [c for c in _commands() if shutil.which(c[0])]
    if not available:
        raise ClipboardError(NO_TOOL)
    for command in available:
        try:
            result = subprocess.run(command, capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            continue
        text = result.stdout.decode("utf-8", errors="replace")
        if result.returncode == 0 and text.strip():
            return text
    raise ClipboardError(EMPTY)
