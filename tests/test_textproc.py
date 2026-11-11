from lorito.textproc import markdown_to_speech, split_sentences


def test_numbered_list_items_keep_number_with_text():
    spoken = markdown_to_speech("Pasos:\n\n1. Instala todo.\n2) Ejecuta las pruebas\n10. Revisa.")
    assert spoken.paragraphs == ["Pasos:", "1: Instala todo.", "2: Ejecuta las pruebas.", "10: Revisa."]


def test_bare_number_is_merged_with_next_sentence():
    assert split_sentences("Paso 1. Haz esto. 2. Luego aquello.") == [
        "Paso 1.", "Haz esto.", "2. Luego aquello."]


def test_code_blocks_are_announced_not_read():
    spoken = markdown_to_speech("Mira:\n\n```python\nx = 1\n```\nFin.")
    assert spoken.code_blocks[0].lines == ["x = 1"]
    assert 1 in spoken.announcements
    assert "x = 1" not in " ".join(spoken.paragraphs)


def test_inline_markdown_is_cleaned():
    spoken = markdown_to_speech("He cambiado **dos** archivos en `src/app.py` ✅ y [la guía](https://x.org/a).")
    assert spoken.paragraphs == ["He cambiado dos archivos en src/app.py y la guía."]
