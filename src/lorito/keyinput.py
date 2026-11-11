"""Lectura del teclado que distingue las teclas del texto pegado.

Con el modo «bracketed paste» activado, la terminal envuelve lo que se pega entre
ESC[200~ y ESC[201~. Así un texto pegado (un error largo, por ejemplo) llega como un
solo bloque y nunca se interpreta como teclas sueltas: sus letras podrían, si no,
permitir un comando, interrumpir a Claude o cerrar lorito.
"""

from __future__ import annotations

import re

ENABLE_PASTE = "\033[?2004h"
DISABLE_PASTE = "\033[?2004l"
PASTE_START, PASTE_END = "\x1b[200~", "\x1b[201~"
ESC = "\x1b"

# Secuencias de teclas especiales (flechas, F1...): CSI, SS3 o Alt+tecla. Se descartan.
_SEQUENCE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1bO.|\x1b[^\[O]", re.S)


class InputParser:
    """Convierte lo leído de la terminal en eventos ("key", tecla) o ("paste", texto).

    `feed` procesa lo que llega; si queda algo a medias (un Escape suelto, una secuencia
    incompleta o un pegado sin terminar), `flush` lo resuelve cuando ya no llega nada más.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._paste: str | None = None

    @property
    def pending(self) -> bool:
        return bool(self._buf) or self._paste is not None

    def feed(self, text: str) -> list[tuple[str, str]]:
        self._buf += text
        events: list[tuple[str, str]] = []
        while self._buf:
            if self._paste is not None:
                end = self._buf.find(PASTE_END)
                if end < 0:
                    # Se guarda un posible final de marca a medias para la próxima lectura.
                    keep = next((n for n in range(len(PASTE_END) - 1, 0, -1)
                                 if self._buf.endswith(PASTE_END[:n])), 0)
                    cut = len(self._buf) - keep
                    self._paste += self._buf[:cut]
                    self._buf = self._buf[cut:]
                    break
                events.append(("paste", _normalize(self._paste + self._buf[:end])))
                self._paste = None
                self._buf = self._buf[end + len(PASTE_END):]
                continue
            if self._buf[0] != ESC:
                events.append(("key", self._buf[0]))
                self._buf = self._buf[1:]
                continue
            if self._buf.startswith(PASTE_START):
                self._paste = ""
                self._buf = self._buf[len(PASTE_START):]
                continue
            if len(self._buf) == 1 or PASTE_START.startswith(self._buf):
                break  # Escape suelto o marca incompleta: se decide en flush o con más datos
            match = _SEQUENCE.match(self._buf)
            if not match:
                break  # secuencia incompleta
            self._buf = self._buf[match.end():]
        return events

    def flush(self) -> list[tuple[str, str]]:
        """Llamar cuando no llega nada más: un Escape suelto es la tecla Escape, y un
        pegado sin marca final (terminal que falla) se da por terminado."""
        events: list[tuple[str, str]] = []
        if self._paste is not None:
            events.append(("paste", _normalize(self._paste + self._buf)))
        elif self._buf == ESC:
            events.append(("key", ESC))
        self._buf, self._paste = "", None
        return events


def _normalize(text: str) -> str:
    # Muchas terminales envían los saltos de línea pegados como retorno de carro.
    return text.replace("\r\n", "\n").replace("\r", "\n")
