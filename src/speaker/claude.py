"""Adaptador para Claude Code usando su modo estructurado (stream-json).

Claude Code se ejecuta en modo no interactivo con entrada y salida JSON por líneas.
Así cada evento indica si es texto de la respuesta, una llamada a herramienta o el
resultado de un comando, y no hay que adivinar qué partes de la pantalla son órdenes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable

BASE_ARGS = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]


@dataclass
class Event:
    kind: str  # "ready" | "text" | "tool" | "done" | "exit"
    text: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    error: bool = False
    denied: list[str] = field(default_factory=list)


class ClaudeSession:
    name = "Claude"

    def __init__(self, executable: str, extra_args: list[str], on_event: Callable[[Event], None]):
        self._on_event = on_event
        self._proc = subprocess.Popen(
            [executable, *BASE_ARGS, *extra_args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def send(self, text: str) -> None:
        message = {"type": "user", "message": {"role": "user",
                                               "content": [{"type": "text", "text": text}]}}
        self._proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.terminate()

    def _read_stderr(self) -> None:
        for line in self._proc.stderr:
            sys.stderr.write(f"[claude] {line}")

    def _read_stdout(self) -> None:
        for line in self._proc.stdout:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            for event in _parse(data):
                self._on_event(event)
        self._proc.wait()
        self._on_event(Event("exit", error=self._proc.returncode != 0))


def _parse(data: dict) -> list[Event]:
    kind = data.get("type")
    if kind == "system" and data.get("subtype") == "init":
        return [Event("ready", text=data.get("model", ""))]
    if kind == "assistant":
        events = []
        for block in data["message"].get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                events.append(Event("text", text=block["text"]))
            elif block.get("type") == "tool_use":
                events.append(Event("tool", tool=block.get("name", ""),
                                    args=block.get("input") or {}))
        return events
    # Los eventos "user" son resultados de herramientas (salida de comandos): no se leen.
    if kind == "result":
        denied = sorted({d.get("tool_name", "") for d in data.get("permission_denials") or []})
        return [Event("done", error=bool(data.get("is_error")), denied=denied)]
    return []
