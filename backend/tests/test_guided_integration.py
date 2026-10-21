import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete

from app.db.models import Document, DocumentChunk
from app.rag.retrieval import retrieval_query

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Requires migrated PostgreSQL"),
]


async def test_catalog_api_topic_persistence_and_validation(resources, monkeypatch):
    app, client, user, other = resources
    catalog = (await client.get("/api/v1/support/topics")).json()
    assert (
        len(catalog) == 8
        and len(next(t for t in catalog if t["topic_id"] == "outros")["questions"]) == 3
    )
    cid = (await client.post("/api/v1/conversations", json={"title": "Guided"})).json()["id"]
    response = await client.patch(
        f"/api/v1/conversations/{cid}/topic", json={"topic_id": "folha_ponto"}
    )
    assert response.status_code == 200 and response.json()["topic_id"] == "folha_ponto"
    assert (await client.get(f"/api/v1/conversations/{cid}")).json()["topic_id"] == "folha_ponto"
    invalid = {
        "request_id": str(uuid.uuid4()),
        "topic_id": "atestados",
        "question_id": "folha_ponto.prazo",
    }
    assert (
        await client.post(f"/api/v1/conversations/{cid}/messages", json=invalid)
    ).status_code == 422
    assert (await client.get(f"/api/v1/conversations/{cid}/messages")).json() == []

    async def no_evidence(*args):
        return []

    monkeypatch.setattr("app.orchestration.graph.retrieve", no_evidence)
    payload = {
        "request_id": str(uuid.uuid4()),
        "topic_id": "folha_ponto",
        "question_id": "folha_ponto.prazo",
    }
    responses = await asyncio.gather(
        *(client.post(f"/api/v1/conversations/{cid}/messages", json=payload) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    rows = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert len(rows) == 2 and rows[0]["content"] == "Qual é o prazo de entrega da folha ponto?"
    assert rows[0]["question_id"] == "folha_ponto.prazo" and rows[0]["topic_id"] == "folha_ponto"
    assert (
        await client.patch(
            f"/api/v1/conversations/{cid}/topic", json={"topic_id": "vale_transporte"}
        )
    ).status_code == 200
    other_question = {
        "request_id": str(uuid.uuid4()),
        "topic_id": "vale_transporte",
        "question_id": "vale_transporte.credito",
    }
    result = (
        await client.post(f"/api/v1/conversations/{cid}/messages", json=other_question)
    ).json()
    assert result["outcome"] == "out_of_scope" and result["sources"] == []
    assert (
        await client.patch(f"/api/v1/conversations/{cid}/topic", json={"topic_id": "outros"})
    ).status_code == 200
    result = (
        await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={
                "request_id": str(uuid.uuid4()),
                "content": "Quem precisa assinar minha folha?",
                "topic_id": "outros",
            },
        )
    ).json()
    assert result["topic_id"] == "folha_ponto"
    from app.auth.dependencies import current_user

    app.dependency_overrides[current_user] = lambda: other
    assert (
        await client.patch(f"/api/v1/conversations/{cid}/topic", json={"topic_id": "folha_ponto"})
    ).status_code == 404


async def test_revoked_profile_and_validation_scope_filters(resources):
    app, _, user, _ = resources
    config = app.state.settings.model_copy(
        update={
            "embedding_model": "acl-test",
            "embedding_dimensions": 4,
            "active_kb_version": "acl-test",
        }
    )
    ids = []
    async with app.state.sessions() as session:
        for changes in [
            {},
            {"status": "revoked"},
            {"status": "pending"},
            {"embedding_profile": "other"},
            {"scope": "restricted"},
            {"validation_only": True},
        ]:
            values = dict(
                name="ACL test",
                media_type="text/plain",
                domain="rh_frequency",
                approved=True,
                status="approved",
                version="acl-test",
                scope="test",
                origin="test",
                storage_key=uuid.uuid4().hex,
                sha256=uuid.uuid4().hex,
                embedding_model="acl-test",
                embedding_dimensions=4,
                embedding_profile=config.embedding_profile,
                is_test=True,
            )
            values.update(changes)
            doc = Document(**values)
            session.add(doc)
            await session.flush()
            ids.append(doc.id)
            session.add(
                DocumentChunk(
                    document_id=doc.id,
                    content="Authorized chunk",
                    chunk_index=0,
                    embedding=[1, 0, 0, 0],
                )
            )
        await session.commit()
        try:
            rows = (
                (
                    await session.execute(
                        retrieval_query([1, 0, 0, 0], config, user.scopes, "rh_frequency")
                    )
                )
                .mappings()
                .all()
            )
            assert {r["document_id"] for r in rows} == {ids[0], ids[5]}
            production = config.model_copy(
                update={"app_env": "production", "dev_document_scopes": []}
            )
            rows = (
                (
                    await session.execute(
                        retrieval_query([1, 0, 0, 0], production, user.scopes, "rh_frequency")
                    )
                )
                .mappings()
                .all()
            )
            assert {r["document_id"] for r in rows} == {ids[0]}
        finally:
            await session.execute(delete(Document).where(Document.id.in_(ids)))
            await session.commit()
