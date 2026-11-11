# Speaker

Aplicación de terminal que convierte en audio el texto generado por asistentes de IA de línea de comandos (como Claude Code, opencode o Hermes), pensada para personas con discapacidad visual o con dificultad para leer grandes volúmenes de texto.

## Objetivo

- Envolver el programa generador de texto: se ejecuta `speaker <orden habitual>`.
- Leer en voz alta las respuestas, sin perder detalle, en varios idiomas.
- Omitir el texto asociado a órdenes y comandos (llamadas a herramientas, salida de comandos, bloques de código), anunciándolos de forma breve.
- Permitir hablarle a la aplicación: transcribir la voz a texto y enviarla como entrada al programa.

## Estado: exploración local, solo CPU, con Claude Code

Esta rama prueba un enfoque 100 % local que no necesita GPU:

- **Lectura:** [Piper](https://github.com/OHF-Voice/piper1-gpl), con detección del idioma de cada frase ([lingua](https://github.com/pemistahl/lingua-py)) para elegir la voz.
- **Dictado:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (modelo `small`, int8). Se pulsa una tecla para empezar y otra vez para terminar.
- **Claude Code:** se ejecuta en modo `stream-json`, así que el texto de la respuesta llega separado de los comandos y de su salida. Los comandos no se leen: solo se anuncian brevemente.

### Requisitos

- Linux con `aplay` y `arecord` (alsa-utils).
- [uv](https://docs.astral.sh/uv/) y Claude Code instalado (`claude`).
- La primera vez se descargan las voces (~60 MB por idioma, en `~/.local/share/speaker/voices`) y el modelo de Whisper (~500 MB).

### Uso

```bash
uv sync
uv run speaker claude                                  # español e inglés
uv run speaker --idiomas es,en,fr claude --model sonnet
uv run speaker claude --permission-mode acceptEdits    # los argumentos tras "claude" se pasan a Claude
uv run speaker --decir "Prueba de voz"                 # probar la voz
uv run pytest                                          # pruebas automáticas
```

| Tecla | Acción |
|---|---|
| Espacio | Empezar / terminar de hablar |
| Enter | Enviar lo dictado (tras escuchar la confirmación) |
| Escape | Callar la lectura o cancelar el dictado |
| E | Escribir un mensaje con el teclado |
| R | Repetir la última respuesta |
| C | Leer el último bloque de código |
| + / - | Cambiar la velocidad |
| H | Ayuda hablada |
| Q | Salir |

Cuando Claude pide permiso para usar una herramienta, speaker emite un pitido y lee la petición:

| Tecla | Acción |
|---|---|
| S | Permitir |
| N | Rechazar: Claude se detiene y espera tus indicaciones |
| T | Permitir siempre, solo durante esta sesión (no se guarda en la configuración) |
| D | Escuchar el detalle: el comando, la ruta o el cambio |
| P | Repetir la pregunta |
| Espacio / E | Responder con la voz o escribiendo: «sí», «no», «siempre», o una indicación (rechaza y se la envía a Claude) |

### Limitaciones conocidas

- Las terminales no informan de cuándo se suelta una tecla, por eso el dictado funciona pulsando una vez para empezar y otra para terminar.
