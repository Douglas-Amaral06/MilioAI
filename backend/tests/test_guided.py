import uuid

import pytest

from app.api.schemas import SendInput
from app.core.errors import AppError
from app.rag.chunking import semantic_chunks
from app.support.catalog import TOPICS, get_topic, resolve_question
from app.support.context import resolve_context


def test_catalog_unique_and_canonical_questions():
    assert len(TOPICS) == 8
    ids = [q.question_id for t in TOPICS for q in t.questions]
    assert len(ids) == len(set(ids))
    assert len(get_topic("outros", ()).questions) == 3
    data = SendInput(
        request_id=uuid.uuid4(), topic_id="folha_ponto", question_id="folha_ponto.prazo"
    )
    assert resolve_question(data, ()) == "Qual é o prazo de entrega da folha ponto?"


@pytest.mark.parametrize(
    "topic,question,content",
    [
        ("atestados", "folha_ponto.prazo", None),
        ("invalido", None, "Teste"),
        ("folha_ponto", "folha_ponto.prazo", "Texto adulterado"),
    ],
)
def test_tampered_catalog_rejected(topic, question, content):
    with pytest.raises(AppError):
        resolve_question(
            SendInput(
                request_id=uuid.uuid4(), topic_id=topic, question_id=question, content=content
            ),
            (),
        )


def test_topic_permission_enforced(monkeypatch):
    import app.support.catalog as catalog

    restricted = TOPICS[0].model_copy(update={"required_scopes": ("private",)})
    monkeypatch.setattr(catalog, "TOPICS", (restricted,))
    with pytest.raises(AppError):
        get_topic("folha_ponto", ())
    assert get_topic("folha_ponto", ("private",)).topic_id == "folha_ponto"


def test_semantic_sections_keep_conditions():
    content = "2. Periodicidade e Prazo\nEnviar até o segundo dia útil.\nEnvio fora do prazo pode resultar em advertência.\n3. Como preencher corretamente\nCaso haja falta no curso, manter CURSO para evitar desconto duplicado."
    rows = list(semantic_chunks([(1, content)]))
    assert len(rows) == 2 and rows[0].section.startswith("2.")
    assert "pode resultar" in rows[0].content
    assert "desconto duplicado" in rows[1].content and rows[1].page == 1
    assert rows == list(semantic_chunks([(1, content)])) and len(rows[0].sha256) == 64


def test_context_switch_followup_and_outros():
    history = [
        {"role": "user", "content": "Qual é o prazo da folha ponto?", "topic_id": "folha_ponto"}
    ]
    assert (
        resolve_context("E se eu atrasar?", "folha_ponto", None, history, ())["topic_id"]
        == "folha_ponto"
    )
    assert (
        resolve_context("Onde é creditado meu vale-transporte?", "folha_ponto", None, history, ())[
            "agent"
        ]
        == "unavailable"
    )
    assert (
        resolve_context("Como solicito minhas férias?", "folha_ponto", None, history, ())[
            "topic_id"
        ]
        == "outros"
    )
    assert (
        resolve_context("Quem precisa assinar minha folha?", "outros", None, history, ())["agent"]
        == "rh_frequency"
    )
    assert resolve_context("???", "outros", None, [], ())["comprehensible"] is False
    assert (
        resolve_context("Onde recebo meu salário?", "salario", "salario.data", [], ())["agent"]
        == "unavailable"
    )
