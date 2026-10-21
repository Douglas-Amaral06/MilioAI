import httpx
import pytest
from sqlalchemy.dialects import postgresql
from test_unit import config

from app.llm.ollama import Ollama
from app.rag.retrieval import retrieval_query
from app.rag.transport_ingest import transport_settings
from app.support.transport import format_answer, identify_card, is_transport


@pytest.mark.parametrize(
    "text",
    [
        "Como solicito a segunda via do meu bilhete?",
        "Perdi meu vale-transporte.",
        "Roubaram meu cartão de ônibus.",
        "Como faço outro Bilhete Único?",
        "Quanto custa a segunda via do VT?",
    ],
)
def test_intent(text):
    assert is_transport(text, {})


def test_followup_and_subject_change():
    state = {"vt_stage": "active", "selected_card_code": "89"}
    assert is_transport("E quanto custa?", state)
    assert is_transport("Qual o prazo de retirada?", state)
    assert is_transport("Qual o valor?", state)
    assert is_transport("Em quantos dias fica pronto?", state)
    assert not is_transport("Qual o prazo da folha ponto?", state)
    assert not is_transport("Onde baixo meu holerite?", state)
    assert not is_transport("Onde vejo minhas férias?", state)


def test_exact_selection_ambiguous_names_and_money():
    rows = [
        {"code": "89", "name": "SPTRANS - Bilhete Único"},
        {"code": "164", "name": "AESA - Bilhete Único Andreense"},
        {"code": "9156", "name": "TOP - Cartão Top"},
    ]
    assert identify_card("Meu cartão é SPTrans", rows) == "89"
    assert identify_card("TOP", rows) == "9156"
    assert identify_card("Bilhete Único", rows) is None
    assert identify_card("custa 89 reais?", rows) is None
    assert identify_card("NãoExiste", rows) is None
    assert identify_card("89", rows) == "89"


def test_filter_exact_code_before_vector_and_namespace(tmp_path):
    settings = transport_settings(config(tmp_path))
    query = retrieval_query(
        [1.0, 0.0],
        settings,
        ("local_review",),
        "beneficios.vale_transporte.segunda_via",
        benefit_code="89",
    )
    sql = str(query.compile(dialect=postgresql.dialect()))
    assert (
        "document_chunks.benefit_code =" in sql
        and "document_chunks.benefit_code ="
        in sql.split("MATERIALIZED")[1].split("SELECT authorized")[0]
    )
    params = query.compile().params
    assert "89" in params.values() and settings.vt_kb_version in params.values()
    assert "document_chunks.attributes" in sql


def test_company_responsibility_and_tariff_units():
    row = {
        "code": "182",
        "uf": "SP",
        "name": "Guarulhos",
        "requester": "Empresa",
        "payer": "Jovem",
        "fee": "6 tarifas",
        "payment": "Dinheiro",
        "procedure": "Retirada com autorização.",
        "review": "",
    }
    text = format_answer(row, ["requester", "payer", "fee", "procedure"])
    assert "solicitação cabe à empresa" in text
    assert "6 tarifas" in text and "R$" not in text
    assert "não foi convertida" in text


async def test_model_field_plan_is_closed(tmp_path):
    async with httpx.AsyncClient(
        base_url="http://test",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"message": {"content": '{"fields":["fee","payment"]}'}}
            )
        ),
    ) as client:
        assert await Ollama(client, config(tmp_path)).transport_fields(
            "Quanto custa?", "Taxa: 7 tarifas"
        ) == ["fee", "payment"]
