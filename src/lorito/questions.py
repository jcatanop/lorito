"""Preguntas con opciones de Claude (herramienta AskUserQuestion).

Claude envía una o varias preguntas, cada una con 2 a 4 opciones, y puede admitir varias
respuestas (multiSelect). Las respuestas se devuelven en `updatedInput.answers`, un
diccionario {texto de la pregunta: respuesta}; las respuestas múltiples van separadas por
comas, y cualquier texto libre vale como la opción "Otro".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TOOL_NAME = "AskUserQuestion"

_NUMBER_WORDS = {
    1: {"1", "uno", "una", "primera", "primero", "one", "first", "premiere", "premier"},
    2: {"2", "dos", "segunda", "segundo", "two", "second", "deux", "seconde", "dois", "duas"},
    3: {"3", "tres", "tercera", "tercero", "three", "third", "trois", "troisieme"},
    4: {"4", "cuatro", "cuarta", "cuarto", "four", "fourth", "quatre", "quatrieme", "quatro"},
    5: {"5", "cinco", "quinta", "quinto", "five", "fifth", "cinq"},
}
_MAX_NUMBER_ANSWER = 6  # palabras; más largo se trata como texto libre


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


def match_options(text: str, labels: list[str]) -> list[int]:
    """Índices (desde 0) de las opciones que nombra el texto: por número ("la dos",
    "opción 3") o por nombre ("SQLite"). Lista vacía si no nombra ninguna."""
    words = _words(text)
    found: list[int] = []
    for i, label in enumerate(labels):
        label_words = _words(label)
        if label_words and _contains(words, label_words):
            found.append(i)
    if found:
        return found
    if len(words) <= _MAX_NUMBER_ANSWER:
        for word in words:
            for number, names in _NUMBER_WORDS.items():
                if word in names and number <= len(labels) and number - 1 not in found:
                    found.append(number - 1)
    return found


def _contains(words: list[str], sub: list[str]) -> bool:
    return any(words[i:i + len(sub)] == sub for i in range(len(words) - len(sub) + 1))


@dataclass
class QuestionFlow:
    """Progreso al responder las preguntas de una petición AskUserQuestion."""

    request: object  # Event de la petición
    index: int = 0
    answers: dict[str, str] = field(default_factory=dict)
    selected: list[int] = field(default_factory=list)

    @property
    def questions(self) -> list[dict]:
        return self.request.args.get("questions") or []

    @property
    def current(self) -> dict:
        return self.questions[self.index]

    @property
    def labels(self) -> list[str]:
        return [o.get("label", "") for o in self.current.get("options") or []]

    @property
    def multi(self) -> bool:
        return bool(self.current.get("multiSelect"))

    def toggle(self, i: int) -> bool:
        """Marca o desmarca una opción; devuelve True si quedó marcada."""
        if i in self.selected:
            self.selected.remove(i)
            return False
        self.selected.append(i)
        return True

    def answer(self, value: str) -> bool:
        """Guarda la respuesta de la pregunta actual; devuelve True si era la última."""
        self.answers[self.current.get("question", "")] = value
        self.index += 1
        self.selected = []
        return self.index >= len(self.questions)

    def answer_options(self, indices: list[int]) -> bool:
        labels = self.labels
        return self.answer(", ".join(labels[i] for i in sorted(indices)))

    def updated_input(self) -> dict:
        return {**self.request.args, "answers": self.answers}
