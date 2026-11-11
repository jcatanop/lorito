"""Convierte el markdown que generan los asistentes en texto apto para ser leído en voz alta.

Los bloques de código no se leen: se sustituyen por un anuncio breve y se guardan
para poder escucharlos a petición.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import messages as msg

_FENCE = re.compile(r"^\s*(```|~~~)\s*([\w+#.-]*)\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BULLET = re.compile(r"^\s*[-*+]\s+(\[[ xX]\]\s+)?")
_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s+")
_BARE_NUMBER = re.compile(r"^\(?\d+[.)]?$")
_QUOTE = re.compile(r"^\s*>\s?")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_URL = re.compile(r"https?://([^/\s)]+)[^\s)]*")
# Rutas de archivo: componentes separados por "/", absolutas (/ o ~/) o relativas. El nombre
# final no termina en punto, para no tragarse el de fin de frase.
_PATH = re.compile(r"(?<![\w/.~-])(~?/)?((?:[\w.@+-]+/)+)([\w@+-]+(?:\.[\w@+-]+)*)?(/?)")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
# Emojis y pictogramas: el sintetizador los lee mal o los ignora.
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f900-\U0001f9ff⬀-⯿️‍]"
)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=\S)")

MAX_CHUNK = 280


@dataclass
class CodeBlock:
    language: str
    lines: list[str]


@dataclass
class Spoken:
    """Resultado de procesar un texto: párrafos para leer y bloques de código omitidos."""

    paragraphs: list[str] = field(default_factory=list)
    # Índices de `paragraphs` que son anuncios de la interfaz (no texto del asistente).
    announcements: set[int] = field(default_factory=set)
    code_blocks: list[CodeBlock] = field(default_factory=list)


def clean_inline(text: str) -> str:
    text = _LINK.sub(lambda m: m.group(1), text)
    text = _URL.sub(lambda m: msg.LINK_TO.format(domain=m.group(1)), text)
    text = _INLINE_CODE.sub(lambda m: m.group(1), text)
    text = _PATH.sub(_short_path, text)
    for _ in range(2):  # énfasis anidado, p. ej. ***texto***
        text = _EMPHASIS.sub(lambda m: m.group(2), text)
    text = _EMOJI.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r" ([.,;:!?])", r"\1", text).strip()


def _short_path(m: re.Match) -> str:
    """Una ruta larga se lee como «nombre, en la carpeta padre»: oír entera una ruta como
    /tmp/claude-1000/proyecto/src/nota.txt es tedioso y no aporta. Las cortas se dejan."""
    absolute, dirs, name = m.group(1), m.group(2).rstrip("/").split("/"), m.group(3)
    if not name:  # termina en "/": es una carpeta
        name, dirs = dirs[-1], dirs[:-1]
    if len(dirs) < (2 if absolute else 3):
        return m.group(0)
    return msg.SHORT_PATH.format(name=name, parent=dirs[-1])


def _table_row(line: str) -> str:
    cells = [clean_inline(c) for c in line.strip().strip("|").split("|")]
    return ", ".join(c for c in cells if c) + "."


def markdown_to_speech(text: str) -> Spoken:
    out = Spoken()
    current: list[str] = []

    def flush() -> None:
        if current:
            para = " ".join(current).strip()
            if para:
                out.paragraphs.append(para)
            current.clear()

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            flush()
            marker, lang = fence.group(1), fence.group(2)
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(marker):
                body.append(lines[i])
                i += 1
            out.code_blocks.append(CodeBlock(lang, body))
            out.announcements.add(len(out.paragraphs))
            out.paragraphs.append(msg.code_block(lang, len(body)))
            i += 1
            continue

        stripped = line.strip()
        if not stripped or _HR.match(line):
            flush()
        elif _TABLE_SEP.match(line):
            pass
        elif stripped.startswith("|"):
            flush()
            out.paragraphs.append(_table_row(stripped))
        elif _HEADING.match(line):
            flush()
            out.paragraphs.append(_end(clean_inline(_HEADING.sub("", line))))
        elif _BULLET.match(line):
            flush()
            current.append(_end(clean_inline(_BULLET.sub("", line))))
            flush()
        elif numbered := _NUMBERED.match(line):
            flush()
            # "1. Texto" se lee como "1: Texto" para que el número no parezca fin de frase.
            item = clean_inline(line[numbered.end():])
            current.append(_end(f"{numbered.group(1)}: {item}"))
            flush()
        else:
            current.append(clean_inline(_QUOTE.sub("", line)))
        i += 1
    flush()
    out.paragraphs = [p for p in out.paragraphs if p.strip(" .")]
    return out


def _end(text: str) -> str:
    """Añade un punto final para que el sintetizador haga una pausa."""
    if text and text[-1] not in ".!?…:;,":
        return text + "."
    return text


def split_sentences(paragraph: str) -> list[str]:
    """Divide un párrafo en frases cortas para empezar a hablar cuanto antes."""
    chunks: list[str] = []
    pieces = _SENTENCE_END.split(paragraph)
    # Un número suelto ("1." o "2)") va con la frase que le sigue, para que se lea
    # en el mismo idioma que ella.
    merged: list[str] = []
    for piece in pieces:
        if merged and _BARE_NUMBER.match(merged[-1].strip()):
            merged[-1] = f"{merged[-1].strip()} {piece}"
        else:
            merged.append(piece)
    for sentence in merged:
        sentence = sentence.strip()
        while len(sentence) > MAX_CHUNK:
            cut = sentence.rfind(", ", 0, MAX_CHUNK)
            if cut < MAX_CHUNK // 3:
                cut = sentence.rfind(" ", 0, MAX_CHUNK)
            if cut <= 0:
                cut = MAX_CHUNK
            chunks.append(sentence[: cut + 1].strip())
            sentence = sentence[cut + 1 :].strip()
        if sentence:
            chunks.append(sentence)
    return chunks
