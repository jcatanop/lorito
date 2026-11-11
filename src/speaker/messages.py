"""Textos de la interfaz. Por ahora solo en español."""

from __future__ import annotations

from pathlib import PurePath

UI_LANG = "es"

READY = "Speaker listo. Pulsa espacio para hablar y hache para escuchar la ayuda."
HELP = (
    "Teclas disponibles. Espacio: empezar o terminar de hablar. "
    "Enter: enviar lo que dictaste. Escape: callar la lectura o cancelar el dictado. "
    "E: escribir un mensaje con el teclado. R: repetir la última respuesta. "
    "C: leer el último bloque de código. Más y menos: cambiar la velocidad. "
    "Q: salir."
)
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
PERMISSION_DENIED = (
    "No se concedió permiso para usar: {tools}. "
    "Puedes iniciar speaker con la opción permission mode, o con allowed tools."
)
AGENT_EXITED = "{agent} se cerró."
TYPE_PROMPT = "Escribe tu mensaje y pulsa Enter: "
GOODBYE = "Hasta luego."
LINK_TO = "enlace a {domain}"


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
