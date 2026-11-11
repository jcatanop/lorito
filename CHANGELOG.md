# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
La versión se define en un solo lugar: `src/lorito/__init__.py`.

## [0.6.0] - 2026-11-11

### Añadido
- Tecla I para interrumpir a Claude mientras trabaja: se detiene, no se lee lo que alcanzó a escribir y queda esperando tus indicaciones. Antes, Escape solo callaba la voz y Claude seguía trabajando.
- Los errores se explican en voz alta: los de la API (modelo inexistente, límite de uso, sesión caducada…) se anuncian como error antes de leer su explicación, y un resultado con error lee su motivo o, si no lo trae, el tipo (máximo de turnos, presupuesto, fallo de ejecución).
- Si Claude se cierra por un error, se lee el último mensaje que escribió (sin las líneas de diagnóstico interno) o su código de salida.
- Aviso de espera: mientras Claude trabaja en silencio suena un tic suave cada 8 segundos y, cada 6 tics, se dice «Claude sigue trabajando». Se ajusta o desactiva con `--aviso-trabajo`.
- Modo plan: al pedir aprobación del plan se lee el plan completo, y la tecla D lo vuelve a leer. Antes solo se oía «usar la herramienta ExitPlanMode» y se aprobaba sin escucharlo.

### Corregido
- Al salir con Q ya no se anuncia que Claude se cerró.

## [0.5.0] - 2026-11-11

### Cambiado
- El proyecto pasa a llamarse **lorito** (antes speaker), por el ave capaz de imitar el habla humana y para no confundirlo con otros proyectos. El comando ahora es `lorito`: hay que desinstalar `speaker` e instalar `lorito` (ver README).
- Las voces se guardan en `~/.local/share/lorito/voices`; las ya descargadas en la carpeta de speaker se mueven solas la primera vez.

## [0.4.0] - 2026-11-11

### Añadido
- Preguntas con opciones de Claude (AskUserQuestion): se leen la pregunta, cada opción numerada y su descripción, con un pitido de aviso. Si hay varias preguntas, se responden una tras otra.
- Respuesta con la tecla del número. En preguntas de varias respuestas, los números marcan o desmarcan y Enter confirma.
- Respuesta por voz o escrita con el número («la dos», «opción 3»), el nombre de la opción («SQLite») o tus propias palabras como respuesta libre.
- La tecla N deja la pregunta sin responder y Claude se detiene a esperar indicaciones.

### Cambiado
- Lo escrito con la tecla E ya no pide confirmación con Enter al responder permisos o preguntas; la confirmación queda para el dictado por voz.

## [0.3.1] - 2026-11-11

### Corregido
- Los números de las listas numeradas se leían en inglés: ahora van unidos a su frase y se leen en el idioma del mensaje.
- Las frases cortas (números, títulos, «Listo.») toman el idioma del mensaje completo de Claude; las descripciones de herramientas, que suelen venir en inglés, ya no cambian el idioma de referencia.

### Añadido
- Pruebas automáticas (`uv run pytest`) del procesado de texto y de la detección de idioma.

## [0.3.0] - 2026-11-11

### Añadido
- Peticiones de permiso de Claude Code leídas en voz alta, con pitido de aviso, y respondidas con teclas: S permitir, N rechazar, T permitir siempre (solo durante la sesión), D escuchar el detalle (comando, ruta o cambio), P repetir la pregunta.
- Respuesta a permisos por voz o escribiendo: «sí», «no», «siempre» (también en inglés, francés y portugués) o una indicación libre, que rechaza la acción y se envía a Claude como mensaje.
- La bienvenida y la ayuda incluyen las teclas de permisos.

### Cambiado
- El anuncio de una herramienta espera un instante: si necesita permiso, solo se oye la pregunta y no un «Ejecutando…» que quizá se rechace.
- Al rechazar, Claude se detiene y espera instrucciones en lugar de terminar con error.

## [0.2.0] - 2026-11-11

### Añadido
- Control de versión: `speaker --version` muestra la versión y, si se ejecuta desde el repositorio, el commit en uso.
- Pantalla de bienvenida con la versión y la tabla de teclas; la bienvenida hablada incluye la versión.
- La tecla H muestra la tabla de teclas además de leerla.

## [0.1.0] - 2026-11-11

### Añadido
- Prototipo local en CPU para Claude Code: lectura con Piper y detección de idioma por frase, dictado con faster-whisper y confirmación antes de enviar.
- Los comandos y su salida no se leen; solo se anuncian. Los bloques de código se omiten y pueden escucharse con la tecla C.
