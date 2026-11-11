# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).
La versión se define en un solo lugar: `src/speaker/__init__.py`.

## [0.2.0] - 2026-11-11

### Añadido
- Control de versión: `speaker --version` muestra la versión y, si se ejecuta desde el repositorio, el commit en uso.
- Pantalla de bienvenida con la versión y la tabla de teclas; la bienvenida hablada incluye la versión.
- La tecla H muestra la tabla de teclas además de leerla.

## [0.1.0] - 2026-11-11

### Añadido
- Prototipo local en CPU para Claude Code: lectura con Piper y detección de idioma por frase, dictado con faster-whisper y confirmación antes de enviar.
- Los comandos y su salida no se leen; solo se anuncian. Los bloques de código se omiten y pueden escucharse con la tecla C.
