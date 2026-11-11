"""Editor de una línea de la tecla E: movimiento, borrado y dibujo en pantalla."""

from lorito.editor import CANCEL, SUBMIT, LineEditor


def editor_with(text, cursor=None):
    e = LineEditor()
    e.insert(text)
    if cursor is not None:
        e.cursor = cursor
    return e


def test_insert_in_the_middle_with_arrows():
    e = editor_with("hola mndo")
    for _ in range(3):
        e.handle("left")
    e.handle("u")
    assert e.text == "hola mundo" and e.cursor == 7


def test_backspace_and_delete_at_cursor():
    e = editor_with("abcd", cursor=2)
    e.handle("\x7f")
    assert (e.text, e.cursor) == ("acd", 1)
    e.handle("delete")
    assert (e.text, e.cursor) == ("ad", 1)


def test_home_end_and_limits():
    e = editor_with("abc")
    e.handle("right")
    assert e.cursor == 3
    e.handle("home")
    e.handle("left")
    assert e.cursor == 0
    e.handle("\x05")  # Ctrl+E
    assert e.cursor == 3


def test_word_jumps_and_word_delete():
    e = editor_with("revisa el archivo config.toml")
    e.handle("word_left")
    assert e.text[e.cursor:] == "toml"
    e.handle("word_left")
    e.handle("word_left")
    assert e.text[e.cursor:] == "archivo config.toml"
    e.handle("word_right")
    assert e.text[:e.cursor] == "revisa el archivo"
    e.handle("\x17")  # Ctrl+W
    assert e.text == "revisa el  config.toml"


def test_kill_to_start_and_to_end():
    e = editor_with("uno dos tres", cursor=4)
    e.handle("\x0b")  # Ctrl+K
    assert e.text == "uno "
    e.handle("\x15")  # Ctrl+U
    assert (e.text, e.cursor) == ("", 0)


def test_enter_and_escape():
    e = editor_with("hola")
    assert e.handle("\n") == SUBMIT
    assert e.handle("\x1b") == CANCEL


def test_render_places_cursor_on_wrapped_rows():
    e = editor_with("x" * 25, cursor=12)  # con "> " ocupa 27 columnas: 3 filas de 10
    out = e.render("> ", 10)
    assert "> " + "x" * 25 in out
    # El cursor está en la columna 14 → fila 1, columna 4; el texto termina en la fila 2.
    assert out.endswith("\r\x1b[1A\x1b[4C")
    assert e.clear() == "\x1b[1A\r\x1b[J"  # vuelve a la primera fila antes de redibujar


def test_render_forces_wrap_when_text_fills_the_row():
    e = editor_with("x" * 8)
    assert " \r" in e.render("> ", 10)


def test_control_characters_are_not_sent_to_the_terminal():
    e = editor_with("a\x1b[31mb\tc")
    out = e.render("> ", 80)
    assert "a·[31mb c" in out
