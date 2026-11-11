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
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

# "--permission-prompt-tool stdio" hace que las peticiones de permiso lleguen como mensajes
# "control_request" por stdout y se respondan con "control_response" por stdin.
BASE_ARGS = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
             "--permission-prompt-tool", "stdio"]

DENY_MESSAGE = ("The user rejected this action. Stop what you are doing and wait for the user "
                "to tell you how to proceed.")


@dataclass
class Event:
    kind: str  # "text" | "tool" | "permission" | "permission_cancel" | "done" | "exit"
    text: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    error: bool = False
    denied: list[str] = field(default_factory=list)
    request_id: str = ""
    tool_use_id: str = ""
    suggestions: list[dict] = field(default_factory=list)
    # "done": tipo de resultado (success, error_during_execution, error_max_turns...).
    # "text": código de error de la API que acompaña al mensaje (model_not_found...).
    # "exit": código de salida del proceso.
    subtype: str = ""


class ClaudeSession:
    name = "Claude"

    def __init__(self, executable: str, extra_args: list[str], on_event: Callable[[Event], None]):
        self._on_event = on_event
        self._proc = subprocess.Popen(
            [executable, *BASE_ARGS, *extra_args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._write_lock = threading.Lock()
        self._stderr_tail: deque[str] = deque(maxlen=20)  # para explicar un cierre con error
        self._closing = False  # el cierre lo pidió lorito: no es un error que anunciar
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def send(self, text: str) -> None:
        self._write({"type": "user", "message": {"role": "user",
                                                 "content": [{"type": "text", "text": text}]}})

    def allow(self, ev: Event, always: bool = False, updated_input: dict | None = None) -> None:
        """Permite el uso de la herramienta. Con `always`, aplica las reglas que sugiere
        Claude, pero solo durante esta sesión (nunca se guardan en archivos de configuración).
        `updated_input` reemplaza los argumentos (p. ej. para añadir respuestas a preguntas)."""
        response = {"behavior": "allow", "updatedInput": updated_input or ev.args}
        if always:
            rules = [dict(s, destination="session") for s in ev.suggestions
                     if s.get("type") in ("addRules", "addDirectories")]
            if rules:
                response["updatedPermissions"] = rules
        self._respond(ev.request_id, response)

    def deny(self, ev: Event) -> None:
        """Rechaza y detiene el turno; Claude espera el siguiente mensaje del usuario."""
        self._respond(ev.request_id, {"behavior": "deny", "message": DENY_MESSAGE,
                                      "interrupt": True})

    def interrupt(self) -> None:
        """Detiene el turno en curso. Claude responde con un resultado de error
        ("error_during_execution") y queda esperando el siguiente mensaje."""
        self._write({"type": "control_request", "request_id": f"lorito-{uuid.uuid4().hex[:12]}",
                     "request": {"subtype": "interrupt"}})

    def _respond(self, request_id: str, response: dict) -> None:
        self._write({"type": "control_response", "response": {
            "subtype": "success", "request_id": request_id, "response": response}})

    def _write(self, data: dict) -> None:
        with self._write_lock:
            try:
                self._proc.stdin.write(json.dumps(data, ensure_ascii=False) + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, ValueError):
                pass  # Claude ya terminó; el evento "exit" lo notificará

    def close(self) -> None:
        self._closing = True
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
            if line.strip():
                self._stderr_tail.append(line.strip())

    def _read_stdout(self) -> None:
        for line in self._proc.stdout:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "control_request" and \
                    data.get("request", {}).get("subtype") != "can_use_tool":
                # Peticiones de control que este adaptador no maneja: responder con error
                # para que Claude no se quede esperando.
                self._write({"type": "control_response", "response": {
                    "subtype": "error", "request_id": data.get("request_id"),
                    "error": "not supported by lorito"}})
                continue
            for event in _parse(data):
                self._on_event(event)
        self._proc.wait()
        code = self._proc.returncode
        if self._closing:
            return
        self._on_event(Event("exit", error=code != 0, subtype=str(code),
                             text="\n".join(self._stderr_tail) if code != 0 else ""))


def _parse(data: dict) -> list[Event]:
    kind = data.get("type")
    if kind == "control_request":
        req = data["request"]
        return [Event("permission", tool=req.get("tool_name", ""), args=req.get("input") or {},
                      text=req.get("description") or "", request_id=data["request_id"],
                      tool_use_id=req.get("tool_use_id", ""),
                      suggestions=req.get("permission_suggestions") or [])]
    if kind == "control_cancel_request":
        return [Event("permission_cancel", request_id=data.get("request_id", ""))]
    if kind == "assistant":
        events = []
        for block in data["message"].get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                events.append(Event("text", text=block["text"], error=bool(data.get("error")),
                                    subtype=data.get("error") or ""))
            elif block.get("type") == "tool_use":
                events.append(Event("tool", tool=block.get("name", ""),
                                    args=block.get("input") or {}, tool_use_id=block.get("id", "")))
        return events
    # Los eventos "user" son resultados de herramientas (salida de comandos): no se leen.
    if kind == "result":
        denied = sorted({d.get("tool_name", "") for d in data.get("permission_denials") or []})
        is_error = bool(data.get("is_error"))
        # En los errores, "result" trae la explicación (en los éxitos repite la respuesta).
        reason = data.get("result") if is_error and isinstance(data.get("result"), str) else ""
        return [Event("done", error=is_error, denied=denied, text=reason,
                      subtype=data.get("subtype") or "")]
    return []
