"""Textos de la interfaz. Por ahora solo en español."""

from __future__ import annotations

import re
from pathlib import PurePath

UI_LANG = "es"

READY = "Speaker versión {version} listo. Pulsa espacio para hablar y hache para escuchar la ayuda."
WELCOME_TITLE = "Speaker {version}"
WELCOME_SUBTITLE = "Lectura en voz alta para {agent}"
KEYS_TITLE = "Teclas"

# (tecla en pantalla, nombre hablado, acción). Única fuente para la bienvenida y la ayuda.
KEYS = [
    ("Espacio", "Espacio", "empezar o terminar de hablar"),
    ("Enter", "Enter", "enviar lo que dictaste"),
    ("Esc", "Escape", "callar la lectura o cancelar el dictado"),
    ("E", "E", "escribir un mensaje con el teclado"),
    ("R", "Erre", "repetir la última respuesta"),
    ("C", "Ce", "leer el último bloque de código"),
    ("+ / -", "Más y menos", "cambiar la velocidad"),
    ("H", "Hache", "escuchar esta ayuda"),
    ("Q", "Cu", "salir"),
]
PERMISSION_KEYS_TITLE = "Cuando Claude pide permiso"
PERMISSION_KEYS = [
    ("S", "Ese", "permitir"),
    ("N", "Ene", "rechazar; Claude se detiene y espera tus indicaciones"),
    ("T", "Te", "permitir siempre durante esta sesión"),
    ("D", "De", "escuchar el detalle (el comando, la ruta o el cambio)"),
    ("P", "Pe", "repetir la pregunta"),
    ("Espacio / E", "Espacio o E", "responder con la voz o escribiendo: sí, no, siempre, "
                                    "o una indicación para Claude"),
]
HELP = ("Teclas disponibles. " + " ".join(f"{spoken}: {action}." for _, spoken, action in KEYS)
        + " Cuando Claude pide permiso: "
        + " ".join(f"{spoken}: {action}." for _, spoken, action in PERMISSION_KEYS))
LOADING_VOICES = "Preparando voces"
LOADING_STT = "Cargando el modelo de reconocimiento de voz"
STT_NOT_READY = "El reconocimiento de voz todavía se está cargando. Espera un momento."
LISTENING = "Te escucho."
TRANSCRIBING = "Transcribiendo"
NOTHING_HEARD = "No entendí nada. Pulsa espacio para intentarlo de nuevo."
HEARD = "Entendí: {text}. Pulsa Enter para enviar, espacio para grabar de nuevo o Escape para cancelar."
SENT = "Enviado."
CANCELLED = "Cancelado."
NOTHING_TO_SEND = "No hay nada para enviar."
NOTHING_TO_REPEAT = "Todavía no hay ninguna respuesta."
NO_CODE = "No hay bloques de código en la última respuesta."
SPEED = "Velocidad {value}."
TURN_DONE = "Listo."
TURN_ERROR = "La tarea terminó con un error."
PERMISSION_DENIED = "No se concedió permiso para usar: {tools}."
PERMISSION_OPTIONS = ("Pulsa ese para permitir, ene para rechazar, te para permitir siempre, "
                      "de para escuchar el detalle, o espacio para responder con la voz.")
PERMISSION_MORE = "Hay {n} permisos más pendientes."
PERMISSION_ALLOWED = "Permitido."
PERMISSION_ALWAYS = "Permitido durante esta sesión."
PERMISSION_DENIED_BY_USER = "Rechazado. Claude se detuvo; pulsa espacio para decirle qué hacer."
PERMISSION_FEEDBACK = "Rechazado. Le envío tu indicación a Claude."
PERMISSION_CANCELLED = "Claude retiró la petición de permiso."
NO_PERMISSION_PENDING = "No hay ninguna petición de permiso pendiente."
HEARD_FEEDBACK = ("Entendí: {text}. Pulsa Enter para rechazar el permiso y enviar esta "
                  "indicación, o Escape para cancelar.")
TURN_STOPPED = "Claude está esperando tus indicaciones."
AGENT_EXITED = "{agent} se cerró."
TYPE_PROMPT = "Escribe tu mensaje y pulsa Enter: "
GOODBYE = "Hasta luego."
LINK_TO = "enlace a {domain}"


def permission_request(name: str, args: dict, description: str) -> tuple[str, str | None, str]:
    """Pregunta de permiso: (frase en el idioma de la interfaz, descripción en cualquier
    idioma, detalle completo para la tecla D)."""
    match name:
        case "Bash":
            return ("Claude pide permiso para ejecutar un comando:",
                    args.get("description") or description, _speakable_command(args.get("command", "")))
        case "Edit" | "MultiEdit":
            path = args.get("file_path", "")
            old, new = args.get("old_string", ""), args.get("new_string", "")
            detail = f"Archivo {path}. " + (f"Reemplaza: {old[:300]}. Por: {new[:300]}." if old or new else "")
            return f"Claude pide permiso para editar el archivo {_name(path)}.", None, detail
        case "Write":
            path = args.get("file_path", "")
            content = args.get("content", "")
            lines = content.count("\n") + 1 if content else 0
            return (f"Claude pide permiso para escribir el archivo {_name(path)}, de {lines} líneas.",
                    None, f"Archivo {path}. Comienza con: {content[:300]}")
        case "NotebookEdit":
            path = args.get("notebook_path", "")
            return f"Claude pide permiso para editar el cuaderno {_name(path)}.", None, f"Archivo {path}."
        case "WebFetch":
            url = args.get("url", "")
            return "Claude pide permiso para consultar una página web.", None, url
        case "WebSearch":
            return "Claude pide permiso para buscar en internet:", args.get("query"), args.get("query", "")
        case _:
            detail = ". ".join(f"{k}: {v}" for k, v in args.items() if isinstance(v, (str, int, float)))
            return (f"Claude pide permiso para usar la herramienta {name.replace('_', ' ')}.",
                    description or None, detail[:600])


def _speakable_command(cmd: str) -> str:
    """Hace legibles en voz alta los operadores más habituales de la shell."""
    for op, word in (("&&", " y luego "), ("||", " o si falla "), ("|", " tubería "),
                     (">>", " añadir a "), (">", " escribir en "), (";", ". ")):
        cmd = cmd.replace(op, word)
    return "El comando es: " + re.sub(r"\s+", " ", cmd).strip()


def code_block(lang: str, n_lines: int) -> str:
    lang_txt = f" en {lang}" if lang else ""
    lines_txt = "una línea" if n_lines == 1 else f"{n_lines} líneas"
    return f"Bloque de código{lang_txt} de {lines_txt}, omitido. Pulsa ce para escucharlo."


def _name(path: str | None) -> str:
    return PurePath(path).name if path else ""


def tool_use(name: str, args: dict) -> tuple[str, str | None]:
    """Devuelve (anuncio en el idioma de la interfaz, detalle opcional en cualquier idioma)."""
    match name:
        case "Bash":
            return "Ejecutando un comando.", args.get("description")
        case "Read":
            return f"Leyendo el archivo {_name(args.get('file_path'))}.", None
        case "Edit" | "MultiEdit" | "NotebookEdit":
            path = args.get("file_path") or args.get("notebook_path")
            return f"Editando el archivo {_name(path)}.", None
        case "Write":
            return f"Escribiendo el archivo {_name(args.get('file_path'))}.", None
        case "Glob":
            return "Buscando archivos.", None
        case "Grep":
            return "Buscando en el contenido de los archivos.", None
        case "WebFetch":
            return "Consultando una página web.", None
        case "WebSearch":
            return "Buscando en internet:", args.get("query")
        case "Task" | "Agent":
            return "Lanzando un subagente:", args.get("description")
        case "TodoWrite":
            return "Actualizando la lista de tareas.", None
        case _:
            return f"Usando la herramienta {name.replace('_', ' ')}.", None
