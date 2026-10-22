import os
import uuid

import pytest
from test_orchestration_reliability import ANSWER, COMPOUND, setup_graph

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL"),
]


async def test_partial_persisted_once_with_only_validated_content(resources, monkeypatch, tmp_path):
    app, client, _, _ = resources
    graph, _ = setup_graph(tmp_path, monkeypatch, [ANSWER], transport_failure=True)
    app.state.graph = graph
    conversation = await client.post("/api/v1/conversations", json={"title": "Reliability"})
    cid = conversation.json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{cid}/stream",
        json={"request_id": str(uuid.uuid4()), "content": COMPOUND},
    )
    assert "event: done" in response.text
    assert "event: error" not in response.text
    rows = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert len(rows) == 2
    assert rows[-1]["status"] == "complete" and rows[-1]["outcome"] == "partial"
    assert [s["id"] for s in rows[-1]["sources"]] == ["frequency-id"]
    assert "Não foi possível concluir esta orientação" in rows[-1]["content"]
