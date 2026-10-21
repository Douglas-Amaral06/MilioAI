import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from test_unit import config

from app.api.schemas import SupportAction
from app.core.errors import AppError
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph
from app.support.operational import (
    CONFIG,
    CONTACT_SCOPE,
    GUIDED,
    INTENTS,
    SERVICES,
    available,
    contact_text,
    detect,
    instructor,
    instructors,
    transition,
    validate_action,
)


def test_directory_exact_and_missing_contact():
    rows = instructors()
    assert len(rows) == 16 and len({row["id"] for row in rows}) == 16
    assert all(set(row) == {"id", "name"} for row in rows)
    assert instructor("instructor-02")["email"] == "marcio.silva@renapsi.org.br"
    assert instructor("instructor-11")["email"] is None
    missing = contact_text("instructor-11")
    assert "educacional.sp@renapsi.org.br" in missing and "leticia@" not in missing
    assert "tel:+5511998030631" in missing and "WhatsApp" not in missing
    with pytest.raises(AppError):
        instructor("unlisted")


def test_action_acl_validation_and_state():
    action = SupportAction(kind="instructor_select", instructor_id="instructor-02")
    with pytest.raises(AppError):
        validate_action(action, {"stage": "selection"}, ())
    with pytest.raises(AppError):
        validate_action(action, {}, (CONTACT_SCOPE,))
    assert "Marcio" in validate_action(action, {"stage": "selection"}, (CONTACT_SCOPE,))
    text, flow = transition(action.model_dump(), {"asked": True, "stage": "selection"})
    assert "marcio.silva@renapsi.org.br" in text and "adriana.correia" not in text
    assert flow["selected_instructor_id"] == "instructor-02"
    text, flow = transition({"kind": "instructor_unknown"}, flow)
    assert "educacional.sp@renapsi.org.br" in text and flow["stage"] == "contact"
    assert available(type("Settings", (), {"app_env": "production"})()) is False


@pytest.mark.parametrize("qid,intent", list(GUIDED.items()))
async def test_guided_bypasses_llm(qid, intent):
    model = AsyncMock()
    assert await detect(model, "ignored", qid, qid.split(".")[0], [], {}) == intent
    model.operational_intent.assert_not_called()


async def test_policy_and_confirmation_do_not_call_model():
    model = AsyncMock()
    assert await detect(model, "Qual o prazo da folha ponto?", None, None, [], {}) == "documental"
    assert (
        await detect(model, "Sim.", None, None, [], {"stage": "confirmation"}) == "instructor_known"
    )
    model.operational_intent.assert_not_called()


async def test_classifier_constrained_output_and_failure(tmp_path):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps({"intent": "payslip"})}})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ollama"
    ) as client:
        model = Ollama(client, config(tmp_path))
        assert (
            await model.operational_intent("Onde baixo meu contracheque?", None, [], INTENTS)
            == "payslip"
        )
        assert captured[0]["format"]["properties"]["intent"]["enum"] == INTENTS
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"message": {"content": '{"intent":"instructor-admin"}'}}
            )
        ),
        base_url="http://ollama",
    ) as client:
        assert (
            await Ollama(client, config(tmp_path)).operational_intent("test", None, [], INTENTS)
            == "documental"
        )


async def test_graph_flow_no_retrieval_repeat_and_topic_switch(tmp_path, monkeypatch):
    model = AsyncMock()
    retrieval = AsyncMock(side_effect=AssertionError("Operational route must not retrieve"))
    monkeypatch.setattr("app.orchestration.graph.retrieve", retrieval)
    graph = build_graph(None, model, config(tmp_path))
    base = {
        "conversation_id": str(uuid.uuid4()),
        "question": "Faltei na capacitação. Onde mando meu atestado?",
        "question_id": None,
        "topic_id": "outros",
        "history": [],
        "scopes": (CONTACT_SCOPE,),
        "support_state": {},
        "chunks": [],
        "sources": [],
    }
    model.operational_intent.return_value = "course_certificate"
    first = await graph.ainvoke(base)
    assert "Você sabe quem é seu instrutor" in first["answer"]
    again = await graph.ainvoke({**base, "support_state": first["support_state"]})
    assert "Você sabe quem é" not in again["answer"]
    model.operational_intent.return_value = "payslip"
    switched = await graph.ainvoke(
        {
            **base,
            "question": "Onde baixo meu holerite?",
            "support_state": {"asked": True, "stage": "selection"},
        }
    )
    assert switched["support_state"]["stage"] == "idle"
    assert CONFIG["portal_url"] in switched["answer"]
    retrieval.assert_not_called()
    for intent in SERVICES:
        model.operational_intent.return_value = intent
        result = await graph.ainvoke(base)
        assert CONFIG["portal_url"] in result["answer"] and result["sources"] == []
    model.operational_intent.return_value = "ambiguous_document"
    assert "Qual documento" in (await graph.ainvoke(base))["answer"]
