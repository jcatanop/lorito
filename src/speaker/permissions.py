"""Interpretación de respuestas habladas o escritas a una petición de permiso."""

from __future__ import annotations

import re
import unicodedata

ALLOW, ALWAYS, DENY, FEEDBACK = "allow", "always", "deny", "feedback"

_YES = {"si", "s", "vale", "ok", "okay", "claro", "adelante", "permitir", "permite", "permitido",
        "hazlo", "dale", "acepto", "aceptar", "yes", "yeah", "sure", "oui", "sim"}
_NO = {"no", "n", "nope", "rechaza", "rechazar", "deniega", "denegar", "cancela", "cancelar",
       "para", "detente", "alto", "stop", "non", "nao"}
_ALWAYS = {"siempre", "always", "toujours", "sempre"}
_MAX_SHORT = 4  # respuestas más largas se tratan como una indicación para Claude


def _normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", text)


def classify(text: str) -> str:
    words = _normalize(text)
    if not words:
        return FEEDBACK
    if len(words) <= _MAX_SHORT:
        if _ALWAYS & set(words) and words[0] not in _NO:
            return ALWAYS
        if words[0] in _YES:
            return ALLOW
        if words[0] in _NO:
            return DENY
    return FEEDBACK
