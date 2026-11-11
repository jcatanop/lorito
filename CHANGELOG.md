# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
La versión se define en un solo lugar: `src/speaker/__init__.py`.

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
