"""Lectura del teclado: teclas, secuencias especiales y texto pegado."""

from lorito.keyinput import InputParser

ERROR = "Traceback (most recent call last):\r  File \"app.py\", line 12\rquit()  # s n t i q"


def test_plain_keys():
    assert InputParser().feed("sq ") == [("key", "s"), ("key", "q"), ("key", " ")]


def test_paste_arrives_as_one_block_not_as_keys():
    events = InputParser().feed("\x1b[200~" + ERROR + "\x1b[201~s")
    assert events == [("paste", ERROR.replace("\r", "\n")), ("key", "s")]


def test_paste_split_across_reads_even_inside_markers():
    p = InputParser()
    chunks = ["\x1b[2", "00~primera\r", "segunda\x1b[2", "01", "~"]
    events = [e for c in chunks for e in p.feed(c)]
    assert events == [("paste", "primera\nsegunda")]
    assert not p.pending


def test_lone_escape_is_resolved_on_flush():
    p = InputParser()
    assert p.feed("\x1b") == []
    assert p.pending
    assert p.flush() == [("key", "\x1b")]


def test_arrow_and_function_keys_are_discarded():
    assert InputParser().feed("\x1bOP\x1b[2~x") == [("key", "x")]


def test_unfinished_paste_is_closed_on_flush():
    p = InputParser()
    assert p.feed("\x1b[200~hola") == []
    assert p.flush() == [("paste", "hola")]


def test_editing_keys_have_names():
    keys = InputParser().feed("\x1b[D\x1b[C\x1bOH\x1b[F\x1b[3~\x1b[1;5D\x1b[1;5C\x1bb\x1b[1~\x1b[4~")
    assert [k for _, k in keys] == ["left", "right", "home", "end", "delete",
                                    "word_left", "word_right", "word_left", "home", "end"]


def test_unknown_sequences_are_still_discarded():
    assert InputParser().feed("\x1bOP\x1b[15~\x1b[2~x") == [("key", "x")]
