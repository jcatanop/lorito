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

# Teclas especiales con nombre (llegan como ("key", nombre)); las demás se descartan.
LEFT, RIGHT, UP, DOWN = "left", "right", "up", "down"
HOME, END, DELETE = "home", "end", "delete"
WORD_LEFT, WORD_RIGHT = "word_left", "word_right"
SPECIAL_KEYS = {LEFT, RIGHT, UP, DOWN, HOME, END, DELETE, WORD_LEFT, WORD_RIGHT}

# Secuencias de teclas especiales (flechas, F1...): CSI, SS3 o Alt+tecla.
_SEQUENCE = re.compile(r"\x1b\[([0-?]*)[ -/]*([@-~])|\x1bO(.)|\x1b([^\[O])", re.S)
_ARROWS = {"D": LEFT, "C": RIGHT, "A": UP, "B": DOWN, "H": HOME, "F": END}
_TILDE = {"1": HOME, "7": HOME, "4": END, "8": END, "3": DELETE}
# Con Ctrl (5) o Alt (3), las flechas laterales saltan de palabra en palabra.
_WORD_MODIFIERS = {"3", "5"}


def _special_key(match: re.Match) -> str | None:
    params, final, ss3, alt = match.groups()
    if ss3:
        return _ARROWS.get(ss3)
    if alt:
        return {"b": WORD_LEFT, "f": WORD_RIGHT}.get(alt)  # Alt+B / Alt+F, como en bash
    numbers = params.split(";")
    if final == "~":
        return _TILDE.get(numbers[0])
    key = _ARROWS.get(final)
    if key in (LEFT, RIGHT) and len(numbers) > 1 and numbers[1] in _WORD_MODIFIERS:
        return WORD_LEFT if key == LEFT else WORD_RIGHT
    return key


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
            if key := _special_key(match):
                events.append(("key", key))
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
