import pytest

from speaker.tts import Speaker


@pytest.fixture(scope="module")
def speaker():
    return Speaker(["es", "en"], {}, default_lang="es")


def test_short_fragments_use_message_language_not_previous_english(speaker):
    speaker.detect("Create empty file uno.txt and verify it exists properly")  # contexto previo en inglés
    plan = speaker.plan("1: Revisa.", fallback="es")
    assert plan == [("1: Revisa.", "es")]


def test_long_sentences_are_detected_individually(speaker):
    plan = speaker.plan("He revisado el archivo de configuración con cuidado. "
                        "The function returns None when the list is empty.", fallback="es")
    assert [lang for _, lang in plan] == ["es", "en"]


def test_tool_descriptions_do_not_change_reference_language(speaker):
    speaker.detect("Estos son los pasos que debes seguir para instalarlo")
    speaker.plan("Create empty file uno.txt and verify it exists properly")  # no fija el idioma
    assert speaker.plan("2: Listo.") == [("2: Listo.", "es")]
