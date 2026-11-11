# Lorito

Aplicación de terminal que convierte en audio el texto generado por asistentes de IA de línea de comandos (como Claude Code, opencode o Hermes), pensada para personas con discapacidad visual o con dificultad para leer grandes volúmenes de texto.

El nombre viene del loro, el ave capaz de imitar el habla humana: lorito repite en voz alta lo que escribe tu asistente.

## Objetivo

- Envolver el programa generador de texto: se ejecuta `lorito <orden habitual>`.
- Leer en voz alta las respuestas, sin perder detalle, en varios idiomas.
- Omitir el texto asociado a órdenes y comandos (llamadas a herramientas, salida de comandos, bloques de código), anunciándolos de forma breve.
- Permitir hablarle a la aplicación: transcribir la voz a texto y enviarla como entrada al programa.

## Estado: exploración local, solo CPU, con Claude Code

Esta rama prueba un enfoque 100 % local que no necesita GPU:

- **Lectura:** [Piper](https://github.com/OHF-Voice/piper1-gpl), con detección del idioma de cada frase ([lingua](https://github.com/pemistahl/lingua-py)) para elegir la voz.
- **Dictado:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (modelo `small`, int8). Se pulsa una tecla para empezar y otra vez para terminar.
- **Claude Code:** se ejecuta en modo `stream-json`, así que el texto de la respuesta llega separado de los comandos y de su salida. Los comandos no se leen: solo se anuncian brevemente.

### Requisitos

- Linux con `aplay` y `arecord`, del paquete alsa-utils:
  ```bash
  sudo apt install alsa-utils      # Debian / Ubuntu
  sudo dnf install alsa-utils      # Fedora
  sudo pacman -S alsa-utils        # Arch
  ```
- [uv](https://docs.astral.sh/uv/), el gestor de Python con el que se instala lorito. uv también se encarga de conseguir una versión de Python adecuada (3.11 o superior):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- Claude Code instalado y con sesión iniciada (el comando `claude` debe funcionar).
- Opcional, para adjuntar el portapapeles con la tecla V: `wl-clipboard` si usas Wayland o `xclip` si usas X11 (`sudo apt install wl-clipboard xclip`).
- La primera vez se descargan las voces (~60 MB por idioma, en `~/.local/share/lorito/voices`) y el modelo de Whisper (~500 MB, en `~/.cache/huggingface`).

### Instalación global

Lorito se instala como una herramienta de uv: queda en su propio entorno aislado y el comando `lorito` se puede usar desde cualquier carpeta.

1. Clona el repositorio en una ubicación permanente (la instalación apunta a esta carpeta, así que no la borres ni la muevas):
   ```bash
   git clone <url-del-repositorio> ~/apps/lorito
   ```
2. Instálalo en modo editable:
   ```bash
   uv tool install --editable ~/apps/lorito
   ```
   En modo editable, el comando usa directamente el código de esa carpeta: si cambias de rama o haces `git pull`, la próxima ejecución ya usa la nueva versión sin reinstalar.
3. Asegúrate de que `~/.local/bin` (donde uv deja el comando) está en el `PATH`. Si `lorito` no se encuentra, ejecuta esto y abre una terminal nueva:
   ```bash
   uv tool update-shell
   ```
4. Comprueba la instalación:
   ```bash
   lorito --version     # p. ej. "lorito 0.5.0 (1a9ae97)": versión y commit en uso
   ```

### Uso en tus proyectos

Entra en la carpeta del proyecto y lanza lorito. Claude Code se ejecuta en esa carpeta, igual que si lo lanzaras directamente:

```bash
cd ~/proyectos/mi-proyecto
lorito claude                                  # español e inglés
lorito --idiomas es,en,fr claude --model sonnet
lorito claude --permission-mode acceptEdits    # los argumentos tras "claude" se pasan a Claude
lorito claude --continue                       # continuar la última conversación de este proyecto
lorito --decir "Prueba de voz"                 # probar la voz
lorito --help                                  # todas las opciones
```

### Actualizar

- **Cambios de código** (`git pull`, cambiar de rama): no hace falta nada; el modo editable los usa al momento.
- **Cambios de dependencias** (si cambia `pyproject.toml`): reinstala para que uv las descargue:
  ```bash
  uv tool install --editable --reinstall ~/apps/lorito
  ```

- **Si tenías instalada la versión anterior, llamada `speaker`:** desinstálala e instala lorito. Las voces ya descargadas se reaprovechan solas:
  ```bash
  uv tool uninstall speaker
  uv tool install --editable ~/apps/lorito
  ```

### Instalación fija (alternativa)

Si prefieres una copia que no cambie aunque modifiques el repositorio, instala sin `--editable`. En ese caso `lorito --version` muestra solo la versión, sin el commit, y para actualizar hay que repetir el comando con `--reinstall`:

```bash
uv tool install ~/apps/lorito
```

### Desinstalar

```bash
uv tool uninstall lorito
rm -rf ~/.local/share/lorito                                  # voces descargadas (opcional)
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-*  # modelos de Whisper (opcional)
```

### Desarrollo

Para trabajar en el código de lorito, desde la carpeta del repositorio:

```bash
uv sync                  # entorno de desarrollo
uv run lorito claude    # ejecutar sin instalar
uv run pytest            # pruebas automáticas
```

### Teclas

| Tecla | Acción |
|---|---|
| Espacio | Empezar / terminar de hablar |
| Enter | Enviar lo dictado (tras escuchar la confirmación) |
| Escape | Callar la lectura, cancelar el dictado o quitar los adjuntos |
| I | Interrumpir a Claude mientras trabaja: se detiene y espera tus indicaciones |
| E | Escribir un mensaje con el teclado (admite texto pegado de varias líneas) |
| V | Adjuntar el texto del portapapeles al próximo mensaje |
| D | Escuchar completos los textos adjuntos |
| R | Repetir la última respuesta |
| C | Leer el último bloque de código |
| + / - | Cambiar la velocidad |
| H | Ayuda hablada |
| Q | Salir. Si Claude está trabajando, pide confirmación: Q otra vez para salir |

Cuando Claude pide permiso para usar una herramienta, lorito emite un pitido y lee la petición:

| Tecla | Acción |
|---|---|
| S | Permitir |
| N | Rechazar: Claude se detiene y espera tus indicaciones |
| T | Permitir siempre, solo durante esta sesión (no se guarda en la configuración) |
| D | Escuchar el detalle: el comando, la ruta, el cambio o el plan |
| P | Repetir la pregunta |
| Espacio / E | Responder con la voz o escribiendo: «sí», «no», «siempre», o una indicación (rechaza y se la envía a Claude) |

Si trabajas en modo plan (`lorito claude --permission-mode plan`), cuando Claude termina el plan lo lee completo antes de pedirte la aprobación: S lo aprueba y Claude empieza a trabajar; N lo rechaza y Claude espera que le digas qué cambiar; D lo lee de nuevo y R también lo repite.

Cuando Claude te pregunta con opciones, lorito lee la pregunta y cada opción numerada con su descripción:

| Tecla | Acción |
|---|---|
| 1 a 9 | Elegir esa opción; si la pregunta admite varias respuestas, marcarla o desmarcarla |
| Enter | Confirmar las opciones marcadas |
| Espacio / E | Responder con la voz o escribiendo: el número («la dos»), el nombre de la opción o tus propias palabras |
| P | Repetir la pregunta |
| N | No responder: Claude se detiene y espera tus indicaciones |

### Adjuntar un texto largo (un error, un registro…)

Para enviarle a Claude un texto copiado, sin tener que dictarlo:

1. Pulsa **V** para adjuntar lo que hay en el portapapeles, o pega directamente en la terminal (Ctrl+Mayús+V). Lorito no lo lee entero: dice cuántas líneas tiene y cómo empieza.
2. Dicta (Espacio) o escribe (E) tu mensaje, por ejemplo «Me sale este error al arrancar». La confirmación avisa de que va con el texto adjunto.
3. Pulsa Enter: Claude recibe tu mensaje y, debajo, el texto adjunto en un bloque aparte. Con Enter sin mensaje se envía solo el adjunto.

Puedes adjuntar varios textos antes de enviar. **D** los lee completos y **Escape** los quita (si algo se está leyendo, el primer Escape lo calla). Si pegas mientras escribes un mensaje con E, un texto corto de una sola línea (un nombre de archivo, por ejemplo) se inserta donde está el cursor; uno largo o de varias líneas se adjunta.

Lo pegado en la terminal nunca se interpreta como teclas, así que sus letras no pueden permitir un comando ni cerrar lorito.

### Escribir un mensaje con la tecla E

Si lo que llega de Claude aparece mientras escribes, se muestra encima y tu línea sigue debajo, sin perder nada.

| Tecla | Acción |
|---|---|
| ← / → | Mover el cursor un carácter |
| Ctrl+← / Ctrl+→ (o Alt+B / Alt+F) | Saltar a la palabra anterior / siguiente |
| Inicio / Fin (o Ctrl+A / Ctrl+E) | Ir al comienzo / al final |
| Retroceso / Supr | Borrar antes / después del cursor |
| Ctrl+W | Borrar la palabra anterior |
| Ctrl+U / Ctrl+K | Borrar hasta el comienzo / hasta el final |
| Enter | Enviar |
| Escape | Cancelar el mensaje |

### Avisos mientras Claude trabaja

Cuando Claude piensa o ejecuta algo largo, puede pasar un rato sin nada que leer. Para que se distinga «sigue trabajando» de «se quedó colgado», lorito emite un tic suave cada 8 segundos de silencio y, cada 6 tics (unos 48 segundos), dice «Claude sigue trabajando». Se ajusta con `--aviso-trabajo SEGUNDOS`; `--aviso-trabajo 0` lo desactiva.

### Compatibilidad con Claude Code

Lorito se comunica con Claude Code a través de su modo `stream-json`, que está poco documentado y puede cambiar entre versiones. La versión con la que se probó está en `TESTED_VERSION` (`src/lorito/claude.py`). Al arrancar, si la versión instalada es otra, lorito lo avisa en voz alta la primera vez para cada versión nueva y, después, solo en pantalla. Tras comprobar que todo funciona con una versión nueva, actualiza `TESTED_VERSION`.

### Limitaciones conocidas

- Las terminales no informan de cuándo se suelta una tecla, por eso el dictado funciona pulsando una vez para empezar y otra para terminar.
