import os
import uuid
from unittest.mock import AsyncMock

import pytest

from app.auth.dependencies import Principal, current_user
from app.support.operational import CONFIG, CONTACT_SCOPE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL"),
]


async def test_persisted_instructor_flow_and_authorization(resources, monkeypatch):
    app, client, user, other = resources
    authorized = Principal(user.id, (*user.scopes, CONTACT_SCOPE))
    app.dependency_overrides[current_user] = lambda: authorized
    classifier = AsyncMock(return_value="course_certificate")
    monkeypatch.setattr(app.state.ollama, "operational_intent", classifier)
    monkeypatch.setattr(
        "app.orchestration.graph.retrieve",
        AsyncMock(side_effect=AssertionError("Unexpected retrieval")),
    )
    directory = await client.get("/api/v1/support/instructors")
    assert directory.status_code == 200 and len(directory.json()) == 16
    assert all(set(row) == {"id", "name"} for row in directory.json())
    cid = (
        await client.post("/api/v1/conversations", json={"title": "Operational integration"})
    ).json()["id"]

    async def send(**values):
        return await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"request_id": str(uuid.uuid4()), **values},
        )

    first = await send(content="Faltei na capacitação. Onde mando meu atestado?")
    assert first.status_code == 201 and CONFIG["portal_url"] in first.json()["content"]

    def get():
        return client.get(f"/api/v1/conversations/{cid}")

    assert (await get()).json()["support_state"]["stage"] == "confirmation"
    topic_before = (await get()).json()["topic_id"]
    assert (await send(action={"kind": "instructor_known"})).status_code == 201
    assert (await get()).json()["topic_id"] == topic_before
    assert (await get()).json()["support_state"]["stage"] == "selection"
    before = len((await client.get(f"/api/v1/conversations/{cid}/messages")).json())
    assert (
        await send(action={"kind": "instructor_select", "instructor_id": "arbitrary-admin"})
    ).status_code == 422
    assert len((await client.get(f"/api/v1/conversations/{cid}/messages")).json()) == before
    contact = await send(action={"kind": "instructor_select", "instructor_id": "instructor-02"})
    assert contact.status_code == 201 and "marcio.silva@renapsi.org.br" in contact.json()["content"]
    assert "adriana.correia" not in contact.json()["content"]
    assert (await get()).json()["support_state"]["selected_instructor_id"] == "instructor-02"
    await send(action={"kind": "instructor_resume"})
    missing = await send(action={"kind": "instructor_select", "instructor_id": "instructor-11"})
    assert "educacional.sp@renapsi.org.br" in missing.json()["content"]
    await send(action={"kind": "instructor_resume"})
    unknown = await send(action={"kind": "instructor_unknown"})
    assert "+55 11 99803-0631" in unknown.json()["content"]
    assert unknown.json()["contacts"][0]["url"] == "https://wa.me/5511998030631"
    reloaded = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert reloaded[-1]["contacts"] == unknown.json()["contacts"]
    await send(action={"kind": "instructor_resume"})
    classifier.return_value = "payslip"
    assert "holerite" in (await send(content="Onde baixo meu holerite?")).json()["content"]
    assert (await get()).json()["support_state"]["stage"] == "idle"
    classifier.return_value = "course_certificate"
    assert (
        "Você sabe quem é"
        not in (await send(content="Onde mando atestado do curso?")).json()["content"]
    )
    await send(action={"kind": "instructor_resume"})
    await send(action={"kind": "instructor_cancel"})
    assert (await get()).json()["support_state"]["stage"] == "idle"
    app.dependency_overrides[current_user] = lambda: user
    assert (await client.get("/api/v1/support/instructors")).status_code == 403
    assert (await send(action={"kind": "instructor_resume"})).status_code == 403
    app.dependency_overrides[current_user] = lambda: other
    assert (await get()).status_code == 404
    app.dependency_overrides.clear()
    assert (await client.get("/api/v1/support/instructors")).status_code == 401
