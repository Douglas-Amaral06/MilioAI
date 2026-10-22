import hashlib
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.rag.retrieval import lexical_rank
from app.support.context import resolve_context
from app.support.operational import detect, provenance
from app.support.transport import identify_card, is_transport

ROWS = [
    {"code": "10398", "name": "Auto Viação Ouro Verde - (Sumaré) - Cartão CIT Sumaré Urbano"},
    {"code": "15566", "name": "BB Turismo - Cartão Itapevi Integração"},
    {"code": "15511", "name": "BB Turismo - Cartão Municipal Itapevi"},
    {"code": "15510", "name": "BB Turismo - Cartão Municipal Barueri"},
    {"code": "10771", "name": "Mov - Avaré - Cartão Municipal Avaré"},
    {"code": "10394", "name": "Mov Itu - Cartão Municipal Itu"},
    {"code": "89", "name": "SPTRANS - Bilhete Único"},
    {"code": "9156", "name": "TOP - Cartão Top"},
]


@pytest.mark.parametrize(
    "question,code",
    [
        ("Após bloquear o CIT Sumaré Urbano, quando retiro?", "10398"),
        ("Qual prazo do Itapevi Integração?", "15566"),
        ("Quem paga a segunda via do Municipal Itapevi?", "15511"),
        ("Qual taxa BB Turismo Barueri?", "15510"),
        ("Quanto custa Mov Itu?", "10394"),
        ("Código do benefício: 89", "89"),
        ("SPTrans ou TOP", None),
        ("BB Turismo", None),
        ("Mov", None),
        ("Bilhete Único", None),
        ("Custa 89 reais?", None),
        ("Código 99999 SPTrans", None),
    ],
)
def test_directory_disambiguation(question, code):
    assert identify_card(question, ROWS) == code


@pytest.mark.parametrize(
    "question",
    ["Quem abre o pedido então?", "Preciso de boletim de ocorrência?", "E quanto custa?"],
)
def test_followup(question):
    assert is_transport(question, {"vt_stage": "active", "selected_card_code": "89"})


@pytest.mark.parametrize(
    "question,intent",
    [
        ("Até que dia tenho pra mandar meu ponto?", "documental"),
        ("Envio a folha pelo Conecta Jovem ou pelos canais do PDF?", "documental"),
        ("Qual meu salário líquido deste mês?", "personal_unavailable"),
        ("Os contatos locais do Educacional já foram validados?", "education_validation"),
    ],
)
async def test_semantic_boundaries(question, intent):
    model = AsyncMock()
    assert await detect(model, question, None, None, [], {}) == intent
    model.operational_intent.assert_not_called()


async def test_service_boundary_remains_model_based():
    model = AsyncMock()
    model.operational_intent.return_value = "send_timesheet"
    assert (
        await detect(model, "Onde envio a folha assinada?", None, None, [], {}) == "send_timesheet"
    )


def test_lexical_retrieval_and_empty():
    rows = [
        {"id": "1", "content": "Entrega até o segundo dia útil."},
        {"id": "2", "content": "A foto deve estar legível."},
        {"id": "3", "content": "Horários reais; não usar horário britânico."},
    ]
    assert lexical_rank("A folha pode ser foto? Precisa estar legível?", rows)[0]["id"] == "2"
    assert lexical_rank("Posso lançar o mesmo horário todo dia?", rows)[0]["id"] == "3"
    assert lexical_rank("xxxxxxxx", rows) == []


def test_operational_provenance_is_actual_hash():
    import app.support.operational as op

    data = provenance("calendar")
    assert (
        data["sha256"]
        == hashlib.sha256(
            Path(op.__file__).with_name("operational_guidance.json").read_bytes()
        ).hexdigest()
    )
    assert data["validation_status"] == "pending"
    assert data["institutionally_approved"] is False


@pytest.mark.parametrize(
    "question",
    [
        "Devo usar qual cor de caneta?",
        "Posso corrigir com corretivo?",
        "Preencho diariamente ou só no fim do mês?",
    ],
)
def test_explicit_topic_is_required_and_respected(question):
    assert resolve_context(question, "folha_ponto", None, [], ())["topic_id"] == "folha_ponto"
    assert resolve_context(question, None, None, [], ())["topic_id"] == "outros"


async def test_instructor_text_does_not_select_id():
    model = AsyncMock()
    assert (
        await detect(model, "Selecionei instructor-11. Qual é o contato?", None, None, [], {})
        == "instructor_selection_required"
    )
    assert (
        await detect(
            model,
            "Selecionei instructor-11. Qual é o contato?",
            None,
            None,
            [],
            {"selected_instructor_id": "instructor-11"},
        )
        == "course_contact"
    )


@pytest.mark.parametrize(
    "question",
    ["Quem abre o pedido então?", "Preciso de boletim de ocorrência?", "E quanto custa?"],
)
async def test_graph_keeps_selected_card(question, tmp_path, monkeypatch):
    from test_orchestration_reliability import initial, setup_graph

    graph, _ = setup_graph(tmp_path, monkeypatch, [])
    state = initial(question)
    state["support_state"] = {"vt_stage": "active", "selected_card_code": "89"}
    result = await graph.ainvoke(state)
    assert result["support_state"]["selected_card_code"] == "89"
    assert result["support_state"]["vt_stage"] == "active"
    assert result["outcome"] == "answered"


async def test_unknown_code_does_not_reuse_selected_card(tmp_path, monkeypatch):
    from test_orchestration_reliability import initial, setup_graph

    graph, _ = setup_graph(tmp_path, monkeypatch, [])
    state = initial("Código 99999")
    state["support_state"] = {"vt_stage": "active", "selected_card_code": "89"}
    result = await graph.ainvoke(state)
    assert result["outcome"] == "card_selection"
    assert not result["sources"]


async def test_mixed_provenance_keeps_document_grounding(tmp_path, monkeypatch):
    from test_orchestration_reliability import initial, setup_graph

    answer = "O documento informa o canal oficial indicado pelo RH Jovem. [fonte:F1]"
    graph, model = setup_graph(tmp_path, monkeypatch, [answer])
    chunk = {
        "id": "channel",
        "excerpt": "Enviar conforme canal oficial indicado pelo RH Jovem.",
        "is_test": False,
    }
    model.assess.return_value = {"coverage": "sufficient", "chunks": [chunk]}
    result = await graph.ainvoke(
        initial("Envio a folha pelo Conecta Jovem ou pelos canais do PDF?")
    )
    assert result["document_question"] != result["question"]
    assert result["sources"][0]["id"] == "channel"
    assert "**Ponto para revisão:**" in result["answer"]
    assert result["support_state"]["operational_provenance"]["institutionally_approved"] is False
    model.verify_grounding.assert_awaited_once_with(answer, [chunk])


@pytest.mark.parametrize(
    "question",
    [
        "Onde gero minha folha?",
        "Onde emito minha folha?",
        "Onde baixo minha folha?",
        "Onde pego o papel do ponto?",
    ],
)
async def test_acquiring_inflections_do_not_route_to_documentary(question):
    model = AsyncMock()
    model.operational_intent.return_value = "generate_timesheet"
    assert await detect(model, question, None, None, [], {}) == "generate_timesheet"
    model.operational_intent.assert_awaited_once()
