from types import SimpleNamespace

from speaker.questions import QuestionFlow, match_options

LABELS = ["PostgreSQL", "SQLite", "MySQL"]


def test_match_by_number_word_or_digit():
    assert match_options("La dos", LABELS) == [1]
    assert match_options("opción 3.", LABELS) == [2]
    assert match_options("la primera", LABELS) == [0]
    assert match_options("two", LABELS) == [1]


def test_match_by_label_ignores_case_and_accents():
    assert match_options("Prefiero sqlite, gracias", LABELS) == [1]
    assert match_options("postgresql y mysql", LABELS) == [0, 2]


def test_number_out_of_range_or_long_text_is_not_an_option():
    assert match_options("la cinco", LABELS) == []
    assert match_options("quiero una base de datos distinta con dos réplicas", LABELS) == []


def test_flow_collects_answers_for_all_questions():
    request = SimpleNamespace(args={"questions": [
        {"question": "¿Base de datos?", "options": [{"label": l} for l in LABELS]},
        {"question": "¿Funciones?", "multiSelect": True,
         "options": [{"label": "Login"}, {"label": "Pagos"}, {"label": "Chat"}]},
    ]})
    flow = QuestionFlow(request)
    assert flow.answer_options([1]) is False
    assert flow.multi
    flow.toggle(2), flow.toggle(0), flow.toggle(1), flow.toggle(1)
    assert flow.answer_options(flow.selected) is True
    assert flow.updated_input()["answers"] == {"¿Base de datos?": "SQLite", "¿Funciones?": "Login, Chat"}
