import json
from unittest.mock import AsyncMock

import httpx
import pytest
from test_unit import config

from app.agents.rh_frequency import NO_EVIDENCE, validate_references
from app.core.errors import ModelError
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph
from app.support.context import resolve_context
from app.support.intents import plan, social_response


class Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


FREQUENCY = {
    "id": "frequency-id",
    "excerpt": "A folha ponto deve ser entregue até o segundo dia útil.",
    "is_test": False,
}
ROW = {
    "name": "Bilhete Único SPTrans",
    "code": "89",
    "uf": "SP",
    "requester": "Jovem",
    "payer": "Jovem",
    "fee": "Sem valor confirmado",
    "payment": "No posto",
    "procedure": "Solicitar no posto.",
}
TRANSPORT = {
    "id": "transport-id",
    "benefit_code": "89",
    "attributes": ROW,
    "excerpt": "Bilhete Único SPTrans 89 SP Jovem Sem valor confirmado No posto Solicitar no posto.",
    "is_test": False,
}
ANSWER = "A folha ponto deve ser entregue até o segundo dia útil. [fonte:F1]"
COMPOUND = "Qual é o prazo para entregar minha folha ponto? E como solicito a segunda via do meu Bilhete Único SPTrans?"


@pytest.mark.parametrize(
    "question", ["Oi", "Olá.", "Bom dia", "Boa tarde", "Tudo bem?", "Obrigado", "Valeu", "Até mais"]
)
async def test_social_bypasses_models_and_retrieval(question, tmp_path):
    model = AsyncMock()
    result = await build_graph(None, model, config(tmp_path)).ainvoke({"question": question})
    assert result["outcome"] == "social"
    assert result["sources"] == []
    assert model.mock_calls == []


@pytest.mark.parametrize(
    "question,count",
    [
        ("Oi, como solicito a segunda via do SPTrans?", 1),
        ("Qual o prazo da Folha Ponto?", 1),
        ("Como solicito a segunda via do SPTrans?", 1),
        (COMPOUND, 2),
        ("Qual o prazo da Folha Ponto e como solicito a segunda via do SPTrans?", 2),
        ("Como solicito a segunda via do SPTrans e quanto custa?", 1),
        ("Qual o prazo da folha ponto? Como solicito SPTrans? Quando recebo salário?", 3),
    ],
)
def test_planning(question, count):
    assert social_response(question) is None
    assert len(plan(question)) == count


def test_ambiguous_and_limit():
    assert plan("Qual o prazo da folha ponto e SPTrans?") is None
    assert (
        plan(
            "Qual o prazo da folha ponto? Como solicito SPTrans? Quando recebo salário? Como solicito férias?"
        )
        is None
    )


def test_changed_topic():
    assert (
        resolve_context("Como solicito SPTrans?", "folha_ponto", None, [], ())["topic_id"]
        == "vale_transporte"
    )
    assert (
        resolve_context("Qual o prazo da folha ponto?", "vale_transporte", None, [], ())["topic_id"]
        == "folha_ponto"
    )


@pytest.mark.parametrize(
    "answer,reason",
    [
        (ANSWER + "\n\nEntregue amanhã.", "Uncited paragraph 2"),
        (ANSWER.replace("F1", "F99"), "invented reference"),
        ("Entregue em 10 dias. [fonte:F1]", "Unsupported number"),
        (ANSWER + "\n\n**Entregue amanhã**", "Uncited paragraph 2"),
    ],
)
def test_reference_failures(answer, reason):
    with pytest.raises(ValueError, match=reason):
        validate_references(answer, [FREQUENCY])


def test_numeric_citation_is_local():
    with pytest.raises(ValueError, match="Unsupported number"):
        validate_references(
            "Prazo 10 dias [fonte:F1]\n\nTaxa 10 [fonte:F2]",
            [FREQUENCY, dict(TRANSPORT, excerpt="Taxa 10")],
        )


def setup_graph(tmp_path, monkeypatch, outputs, *, supported=True, transport_failure=False):
    model = AsyncMock()
    model.operational_intent.return_value = "documental"
    model.assess.return_value = {"coverage": "sufficient", "chunks": [FREQUENCY]}
    model.verify_grounding.return_value = supported
    model.transport_fields.return_value = ["procedure"]
    generated = iter(outputs)

    async def chat(messages):
        yield next(generated, NO_EVIDENCE)

    model.chat = chat

    async def retrieve(*args, **kwargs):
        if kwargs.get("benefit_code"):
            if transport_failure:
                raise ModelError()
            assert args[4] == ("test",)
            return [TRANSPORT]
        assert args[4] == ("test",)
        assert args[5] == "rh_frequency"
        return [FREQUENCY]

    monkeypatch.setattr("app.orchestration.graph.retrieve", retrieve)
    monkeypatch.setattr(
        "app.orchestration.graph.cards",
        AsyncMock(return_value=[{"code": "89", "name": ROW["name"], "uf": "SP"}]),
    )
    return build_graph(Session, model, config(tmp_path)), model


def initial(question):
    return {
        "question": question,
        "history": [],
        "scopes": ("test",),
        "support_state": {},
        "conversation_id": "test",
    }


@pytest.mark.parametrize(
    "first,second,expected",
    [
        ("Entregue amanhã.", ANSWER, ANSWER),
        ("Entregue amanhã.", "Sem fonte novamente.", NO_EVIDENCE),
    ],
)
async def test_repair_and_buffering(tmp_path, monkeypatch, first, second, expected):
    graph, _ = setup_graph(tmp_path, monkeypatch, [first, second])
    events = [
        event
        async for event in graph.astream(
            initial("Qual o prazo da folha ponto?"), stream_mode="custom"
        )
    ]
    assert "".join(e.get("text", "") for e in events) == expected
    assert first not in json.dumps(events, ensure_ascii=False)


async def test_semantic_rejection(tmp_path, monkeypatch):
    graph, model = setup_graph(tmp_path, monkeypatch, [ANSWER, ANSWER], supported=False)
    result = await graph.ainvoke(initial("Qual o prazo da folha ponto?"))
    assert result["answer"] == NO_EVIDENCE
    assert not result["sources"]
    assert model.verify_grounding.await_count == 2


@pytest.mark.parametrize("failure", [False, True])
async def test_compound_and_partial_sources(tmp_path, monkeypatch, failure):
    graph, _ = setup_graph(tmp_path, monkeypatch, [ANSWER], transport_failure=failure)
    result = await graph.ainvoke(initial(COMPOUND))
    assert "[fonte:frequency-id]" in result["answer"]
    assert "[fonte:F1]" not in result["answer"]
    assert result["outcome"] == ("partial" if failure else "answered")
    assert {s["id"] for s in result["sources"]} == (
        {"frequency-id"} if failure else {"frequency-id", "transport-id"}
    )
    first, second = result["answer"].split("**Benefício Vale-Transporte**")
    assert "transport-id" not in first
    assert "frequency-id" not in second


async def test_three_intents_execute_sequentially(tmp_path, monkeypatch):
    graph, _ = setup_graph(tmp_path, monkeypatch, [ANSWER])
    result = await graph.ainvoke(initial(COMPOUND + " Quando recebo salário?"))
    assert result["outcome"] == "partial"
    assert "frequency-id" in result["answer"] and "transport-id" in result["answer"]
    assert "**Salário**" in result["answer"]


async def test_restricted_topic_preserves_other_intent(tmp_path, monkeypatch):
    import app.support.catalog as catalog

    graph, _ = setup_graph(tmp_path, monkeypatch, [ANSWER])
    monkeypatch.setattr(
        catalog,
        "TOPICS",
        tuple(
            t.model_copy(update={"required_scopes": ("private",)})
            if t.topic_id == "vale_transporte"
            else t
            for t in catalog.TOPICS
        ),
    )
    result = await graph.ainvoke(initial(COMPOUND))
    assert result["outcome"] == "partial"
    assert [s["id"] for s in result["sources"]] == ["frequency-id"]


async def test_verifier_only_receives_cited_evidence(tmp_path):
    def respond(request):
        payload = json.loads(request.content)
        claims = json.loads(payload["messages"][-1]["content"])
        assert claims[0]["evidence"] == [FREQUENCY["excerpt"]]
        assert TRANSPORT["excerpt"] not in claims[0]["evidence"]
        return httpx.Response(200, json={"message": {"content": '{"supported": false}'}})

    async with httpx.AsyncClient(
        base_url="http://test", transport=httpx.MockTransport(respond)
    ) as client:
        assert not await Ollama(client, config(tmp_path)).verify_grounding(
            ANSWER, [FREQUENCY, TRANSPORT]
        )
