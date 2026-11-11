"""Textos de la interfaz. Por ahora solo en español."""

from __future__ import annotations

import re
from pathlib import PurePath

UI_LANG = "es"
PLAN_TOOL = "ExitPlanMode"  # Claude sale del modo plan y pide aprobar el plan

READY = "Lorito versión {version} listo. Pulsa espacio para hablar y hache para escuchar la ayuda."
WELCOME_TITLE = "Lorito {version}"
WELCOME_SUBTITLE = "Lectura en voz alta para {agent}"
KEYS_TITLE = "Teclas"

# (tecla en pantalla, nombre hablado, acción). Única fuente para la bienvenida y la ayuda.
KEYS = [
    ("Espacio", "Espacio", "empezar o terminar de hablar"),
    ("Enter", "Enter", "enviar lo que dictaste"),
    ("Esc", "Escape", "callar la lectura, cancelar el dictado o quitar los adjuntos"),
    ("I", "I", "interrumpir a Claude mientras trabaja"),
    ("E", "E", "escribir un mensaje con el teclado"),
    ("V", "Uve", "adjuntar el texto del portapapeles al próximo mensaje"),
    ("D", "De", "escuchar completos los textos adjuntos"),
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
    ("D", "De", "escuchar el detalle (el comando, la ruta, el cambio o el plan)"),
    ("P", "Pe", "repetir la pregunta"),
    ("Espacio / E", "Espacio o E", "responder con la voz o escribiendo: sí, no, siempre, "
                                    "o una indicación para Claude"),
]
QUESTION_KEYS_TITLE = "Cuando Claude te pregunta con opciones"
QUESTION_KEYS = [
    ("1 a 9", "Los números", "elegir esa opción; si admite varias, marcarla o desmarcarla"),
    ("Enter", "Enter", "confirmar las opciones marcadas"),
    ("Espacio / E", "Espacio o E", "responder con la voz o escribiendo: el número, el nombre "
                                    "de la opción o tus propias palabras"),
    ("P", "Pe", "repetir la pregunta"),
    ("N", "Ene", "no responder; Claude se detiene y espera tus indicaciones"),
]
HELP = ("Teclas disponibles. " + " ".join(f"{spoken}: {action}." for _, spoken, action in KEYS)
        + " Cuando Claude pide permiso: "
        + " ".join(f"{spoken}: {action}." for _, spoken, action in PERMISSION_KEYS)
        + " Cuando Claude te pregunta con opciones: "
        + " ".join(f"{spoken}: {action}." for _, spoken, action in QUESTION_KEYS))
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
TURN_ERROR_REASON = "La tarea terminó con un error:"
CLAUDE_ERROR = "Claude informa de un error:"
# Motivo de un resultado con error cuando Claude no da explicación.
ERROR_SUBTYPES = {
    "error_max_turns": "La tarea se detuvo: se alcanzó el número máximo de turnos.",
    "error_max_budget_usd": "La tarea se detuvo: se alcanzó el presupuesto máximo.",
    "error_during_execution": "La tarea se detuvo por un fallo durante la ejecución.",
}
PERMISSION_DENIED = "No se concedió permiso para usar: {tools}."
PERMISSION_OPTIONS = ("Pulsa ese para permitir, ene para rechazar, te para permitir siempre, "
                      "de para escuchar el detalle, o espacio para responder con la voz.")
PLAN_OPTIONS = ("Pulsa ese para aprobar el plan, ene para rechazarlo y decirle a Claude qué "
                "cambiar, de para escucharlo otra vez, o espacio para responder con la voz.")
PLAN_APPROVED = "Plan aprobado. Claude empieza a trabajar."
PERMISSION_MORE = "Hay {n} permisos más pendientes."
PERMISSION_ALLOWED = "Permitido."
PERMISSION_ALWAYS = "Permitido durante esta sesión."
PERMISSION_DENIED_BY_USER = "Rechazado. Claude se detuvo; pulsa espacio para decirle qué hacer."
PERMISSION_FEEDBACK = "Rechazado. Le envío tu indicación a Claude."
PERMISSION_CANCELLED = "Claude retiró la petición de permiso."
NO_PERMISSION_PENDING = "No hay ninguna petición de permiso pendiente."
HEARD_FEEDBACK = ("Entendí: {text}. Pulsa Enter para rechazar el permiso y enviar esta "
                  "indicación, o Escape para cancelar.")
INTERRUPTING = "Deteniendo a Claude."
INTERRUPTED = "Claude se detuvo. Pulsa espacio para decirle qué hacer."
NOT_WORKING = "Claude no está trabajando ahora."
STILL_WORKING = "Claude sigue trabajando."
TURN_STOPPED = "Claude está esperando tus indicaciones."
QUESTION_INTRO = "Claude te pregunta:"
QUESTION_INTRO_N = "Claude te pregunta, pregunta {i} de {n}:"
OPTION = "Opción {n}: {label}."
QUESTION_HELP_SINGLE = ("Pulsa el número de la opción, o espacio para responder con la voz, "
                        "diciendo el número, el nombre de la opción o tus propias palabras.")
QUESTION_HELP_MULTI = ("Puedes elegir varias. Pulsa los números para marcarlas o desmarcarlas, "
                       "y Enter para confirmar. O pulsa espacio para responder con la voz.")
QUESTION_HOW = "Responde con el número de la opción, o pulsa pe para repetir la pregunta."
OPTION_CHOSEN = "Elegiste: {labels}."
OPTION_MARKED = "{label}, marcada."
OPTION_UNMARKED = "{label}, desmarcada."
OPTIONS_MARKED = "Marcadas: {labels}. Pulsa Enter para confirmar."
NONE_MARKED = "No marcaste ninguna opción. Pulsa los números para marcarlas."
NO_SUCH_OPTION = "No hay opción {n}."
ANSWERS_SENT = "Respuestas enviadas a Claude."
QUESTION_DECLINED = "No respondiste. Claude se detuvo; pulsa espacio para decirle qué hacer."
HEARD_ANSWER = ("Entendí: {text}. No coincide con ninguna opción. Pulsa Enter para enviarlo "
                "como tu respuesta, o Escape para cancelar.")
AGENT_EXITED = "{agent} se cerró."
AGENT_EXITED_ERROR = "{agent} se cerró por un error, con código {code}."
AGENT_EXITED_REASON = "{agent} se cerró por un error. El último mensaje fue:"
TYPE_PROMPT = "Escribe tu mensaje y pulsa Enter: "
FROM_CLIPBOARD = "del portapapeles"
PASTED = "pegado"
ATTACHED = "Adjunté el texto {source}, de {lines}. Empieza con:"
ATTACHED_TOTAL = "Ya hay {count}."
ATTACH_HINT = ("Ahora dicta o escribe tu mensaje, o pulsa Enter para enviarlo solo. "
               "Pulsa de para escucharlo completo, o Escape para quitarlo.")
WITH_ATTACHMENTS = "Con {count}."
ATTACHMENT_N = "Adjunto {n}."
ATTACHMENTS_REMOVED = "Adjuntos quitados."
CANCELLED_KEEP_ATTACHMENTS = "Cancelado. Lo adjunto sigue preparado; Escape otra vez lo quita."
CLIPBOARD_EMPTY = "El texto está vacío; no adjunté nada."


def lines_count(n: int) -> str:
    return "una línea" if n == 1 else f"{n} líneas"


def attachments_count(n: int) -> str:
    return "un texto adjunto" if n == 1 else f"{n} textos adjuntos"
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
        case "ExitPlanMode":
            # El detalle es el plan en markdown: se lee completo, no se resume.
            return ("Claude terminó su plan y pide tu aprobación para ponerlo en marcha. El plan es:",
                    None, args.get("plan") or "")
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
        case "AskUserQuestion":
            return "Claude te hace una pregunta.", None
        case "TodoWrite":
            return "Actualizando la lista de tareas.", None
        case "ExitPlanMode":
            return "Claude presenta su plan:", None
        case _:
            return f"Usando la herramienta {name.replace('_', ' ')}.", None
