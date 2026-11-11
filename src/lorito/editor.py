"""Editor de una línea para escribir mensajes con la tecla E.

Admite mover el cursor (flechas, Inicio, Fin, Ctrl+flechas para saltar palabras) y
borrar en cualquier posición. Se redibuja entero tras cada tecla, teniendo en cuenta
que el texto puede ocupar varias filas de la terminal.
"""

from __future__ import annotations

import unicodedata

from .keyinput import DELETE, END, HOME, LEFT, RIGHT, WORD_LEFT, WORD_RIGHT

SUBMIT, CANCEL = "submit", "cancel"

CTRL_A, CTRL_E, CTRL_K, CTRL_U, CTRL_W = "\x01", "\x05", "\x0b", "\x15", "\x17"
BACKSPACE = ("\x7f", "\b")


def _shown(ch: str) -> str:
    """Carácter con el que se muestra cada uno del texto (siempre uno por uno, para que
    las posiciones coincidan): los de control no deben llegar a la terminal."""
    if ch == "\t":
        return " "
    if unicodedata.category(ch) == "Cc":
        return "·"
    return ch


def _width(text: str) -> int:
    """Columnas que ocupa un texto en la terminal (los caracteres anchos ocupan dos)."""
    total = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


class LineEditor:
    def __init__(self) -> None:
        self.text = ""
        self.cursor = 0
        self._row = 0  # fila (desde el comienzo de la línea) donde quedó el cursor

    # ---- edición -------------------------------------------------------------
    def insert(self, text: str) -> None:
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def handle(self, key: str) -> str | None:
        """Aplica una tecla. Devuelve SUBMIT (Enter), CANCEL (Escape) o None."""
        text, cur = self.text, self.cursor
        if key in ("\n", "\r"):
            return SUBMIT
        if key == "\x1b":
            return CANCEL
        if key in BACKSPACE:
            if cur:
                self.text, self.cursor = text[:cur - 1] + text[cur:], cur - 1
        elif key == DELETE:
            self.text = text[:cur] + text[cur + 1:]
        elif key == LEFT:
            self.cursor = max(0, cur - 1)
        elif key == RIGHT:
            self.cursor = min(len(text), cur + 1)
        elif key in (HOME, CTRL_A):
            self.cursor = 0
        elif key in (END, CTRL_E):
            self.cursor = len(text)
        elif key == WORD_LEFT:
            self.cursor = self._word_start(cur)
        elif key == WORD_RIGHT:
            self.cursor = self._word_end(cur)
        elif key == CTRL_U:  # borrar desde el comienzo hasta el cursor
            self.text, self.cursor = text[cur:], 0
        elif key == CTRL_K:  # borrar desde el cursor hasta el final
            self.text = text[:cur]
        elif key == CTRL_W:  # borrar la palabra anterior
            start = self._word_start(cur)
            self.text, self.cursor = text[:start] + text[cur:], start
        elif len(key) == 1 and key.isprintable():
            self.insert(key)
        return None

    def _word_start(self, pos: int) -> int:
        while pos and not self.text[pos - 1].isalnum():
            pos -= 1
        while pos and self.text[pos - 1].isalnum():
            pos -= 1
        return pos

    def _word_end(self, pos: int) -> int:
        n = len(self.text)
        while pos < n and not self.text[pos].isalnum():
            pos += 1
        while pos < n and self.text[pos].isalnum():
            pos += 1
        return pos

    # ---- pantalla ------------------------------------------------------------
    def clear(self) -> str:
        """Secuencia que borra la línea del editor y deja el cursor donde comenzaba."""
        up = f"\x1b[{self._row}A" if self._row else ""
        self._row = 0
        return f"{up}\r\x1b[J"

    def render(self, prompt: str, width: int) -> str:
        """Secuencia que redibuja la indicación y el texto, y coloca el cursor."""
        width = max(width, 10)
        shown = prompt + "".join(_shown(ch) for ch in self.text)
        total = _width(shown)
        at = _width(prompt) + _width(shown[len(prompt):len(prompt) + self.cursor])
        out = [self.clear(), shown]
        if total % width == 0:
            # La terminal no baja de fila hasta escribir otro carácter: se fuerza el salto
            # para que el cursor pueda quedar al final.
            out.append(" \r")
        end_row = total // width
        row, col = divmod(at, width)
        out.append("\r")
        if end_row > row:
            out.append(f"\x1b[{end_row - row}A")
        if col:
            out.append(f"\x1b[{col}C")
        self._row = row
        return "".join(out)
