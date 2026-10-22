import os
import uuid

import pytest
from sqlalchemy import delete

from app.api.schemas import SendInput
from app.auth.dependencies import current_user
from app.db.models import Document, DocumentChunk, Message, User
from app.messages.service import execute, prepare
from app.orchestration.graph import build_graph
from app.rag.retrieval import retrieval_query

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 with migrated PostgreSQL"
    ),
]


async def create(client):
    result = await client.post("/api/v1/conversations", json={"title": "Test"})
    assert result.status_code == 201, result.text
    return result.json()["id"]


async def test_crud_validation_isolation_upload(resources):
    app, client, user, other = resources
    cid = await create(client)
    assert (await client.post("/api/v1/conversations", json={"title": " "})).status_code == 422
    assert (await client.get("/api/v1/conversations?limit=101")).status_code == 422
    assert (await client.patch(f"/api/v1/conversations/{cid}", json={"title": "Renamed"})).json()[
        "title"
    ] == "Renamed"
    assert (await client.get(f"/api/v1/conversations/{cid}")).json()["title"] == "Renamed"
    result = await client.post(
        f"/api/v1/conversations/{cid}/attachments",
        files={"file": ("../note.txt", b"Attachment test", "text/plain")},
    )
    assert result.status_code == 201, result.text
    aid = result.json()["id"]
    assert result.json()["name"] == "note.txt"
    assert (
        await client.get(f"/api/v1/conversations/{cid}/attachments/{aid}")
    ).content == b"Attachment test"
    assert (
        await client.post(
            f"/api/v1/conversations/{cid}/attachments", files={"file": ("bad.exe", b"MZ")}
        )
    ).status_code == 415
    assert (
        await client.post(
            f"/api/v1/conversations/{cid}/attachments", files={"file": ("bad.pdf", b"%PDF-invalid")}
        )
    ).status_code == 422
    app.dependency_overrides[current_user] = lambda: other
    for path in [
        f"/conversations/{cid}",
        f"/conversations/{cid}/messages",
        f"/conversations/{cid}/attachments/{aid}",
    ]:
        assert (await client.get("/api/v1" + path)).status_code == 404
    assert (
        await client.patch(f"/api/v1/conversations/{cid}", json={"title": "Intrusion"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/conversations/{cid}")).status_code == 404
    assert (await client.get("/api/v1/conversations")).json() == []
    app.dependency_overrides[current_user] = lambda: user
    assert (
        await client.delete(f"/api/v1/conversations/{cid}/attachments/{aid}")
    ).status_code == 204
    assert (await client.delete(f"/api/v1/conversations/{cid}")).status_code == 204


async def test_pgvector_filters_real_database(resources):
    app, _, user, _ = resources
    config = app.state.settings.model_copy(
        update={
            "embedding_model": "test-space",
            "embedding_dimensions": 4,
            "active_kb_version": "unit-v1",
        }
    )
    ids = []
    async with app.state.sessions() as session:
        for changes in [
            {},
            {"approved": False},
            {"scope": "other"},
            {"domain": "benefits"},
            {"version": "old"},
            {"embedding_model": "different"},
        ]:
            values = dict(
                name="Test",
                media_type="text/plain",
                domain="rh_frequency",
                approved=True,
                version="unit-v1",
                scope="test",
                origin="test",
                storage_key=uuid.uuid4().hex,
                sha256=uuid.uuid4().hex,
                embedding_model="test-space",
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
                    content="Point record",
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
            assert [r["document_id"] for r in rows] == [ids[0]]
            rows = (
                await session.execute(
                    retrieval_query([0, 1, 0, 0], config, user.scopes, "rh_frequency")
                )
            ).all()
            assert rows == []
        finally:
            await session.execute(delete(Document).where(Document.id.in_(ids)))
            await session.commit()


async def test_stream_persistence_idempotency_and_cancellation(resources, monkeypatch):
    app, client, user, other = resources
    cid = uuid.UUID(await create(client))
    chunk = {
        "id": str(uuid.uuid4()),
        "document_id": str(uuid.uuid4()),
        "title": "Fictício",
        "version": "test-v1",
        "page": 1,
        "chunk": 0,
        "excerpt": "Fictício: registro de ponto em 3 dias.",
        "is_test": True,
    }

    async def retrieve(*args, **kwargs):
        return [chunk]

    monkeypatch.setattr("app.orchestration.graph.retrieve", retrieve)

    class Model:
        async def select_document_rule(self, question, rules):
            return rules[0]["id"]

        async def operational_intent(self, *args):
            return "documental"

        async def assess(self, question, chunks, topic):
            return {"coverage": "sufficient", "chunks": chunks}

        async def verify_grounding(self, answer, chunks):
            return True

        async def chat(self, messages):
            for part in ["Material fictício de teste: ", f"3 dias. [fonte:{chunk['id']}]"]:
                yield part

    app.state.graph = build_graph(app.state.sessions, Model(), app.state.settings)
    payload = {"request_id": str(uuid.uuid4()), "content": "Qual prazo do atestado do trabalho?"}
    response = await client.post(f"/api/v1/conversations/{cid}/stream", json=payload)
    assert response.status_code == 200
    assert all(
        f"event: {event}" in response.text for event in ["start", "delta", "sources", "done"]
    )
    assert (
        await client.post(f"/api/v1/conversations/{cid}/stream", json=payload)
    ).status_code == 409
    history = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert (
        len(history) == 2
        and history[-1]["status"] == "complete"
        and history[-1]["sources"][0]["id"] == chunk["id"]
    )
    async with app.state.sessions() as session:
        assert (await session.get(Message, uuid.UUID(history[-1]["id"]))).content
    data = SendInput(request_id=uuid.uuid4(), content="Ponto")
    prepared = await prepare(app.state.sessions, user, cid, data, app.state.settings)
    iterator = execute(app, user, cid, data, prepared)
    assert (await anext(iterator))["event"] == "start"
    assert (await anext(iterator))["event"] == "delta"
    await iterator.aclose()
    async with app.state.sessions() as session:
        message = await session.get(Message, prepared[1].id)
        assert message.status == "cancelled" and message.content == ""
    app.dependency_overrides[current_user] = lambda: other
    assert (
        await client.post(
            f"/api/v1/conversations/{cid}/messages",
            json={"request_id": str(uuid.uuid4()), "content": "Ponto"},
        )
    ).status_code == 404


async def test_stream_model_failure(resources, monkeypatch):
    app, client, _, _ = resources
    cid = await create(client)

    async def fail(*args):
        from app.core.errors import ModelError

        raise ModelError()

    monkeypatch.setattr("app.orchestration.graph.retrieve", fail)
    response = await client.post(
        f"/api/v1/conversations/{cid}/stream",
        json={"request_id": str(uuid.uuid4()), "content": "Ponto"},
    )
    assert "event: error" in response.text and "event: done" not in response.text
    rows = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
    assert rows[-1]["status"] == "failed" and not rows[-1]["content"]


async def test_signed_jwt_authentication_and_ownership(resources):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    app, client, _, _ = resources
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    issuer = "https://auth.example/auth/v1"
    app.state.settings.auth_mode = "jwt"
    app.state.settings.jwt_issuer = issuer

    class Keys:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=key.public_key())

    app.state.jwks = Keys()
    app.dependency_overrides.clear()
    subjects = [str(uuid.uuid4()), str(uuid.uuid4())]
    tokens = [
        jwt.encode(
            {
                "sub": sub,
                "iss": issuer,
                "aud": "authenticated",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            key,
            algorithm="RS256",
        )
        for sub in subjects
    ]
    client.headers["Authorization"] = "Bearer " + tokens[0]
    cid = await create(client)
    assert (await client.get(f"/api/v1/conversations/{cid}")).status_code == 200
    client.headers["Authorization"] = "Bearer " + tokens[1]
    assert (await client.get(f"/api/v1/conversations/{cid}")).status_code == 404
    assert (await client.delete(f"/api/v1/conversations/{cid}")).status_code == 404
    async with app.state.sessions() as session:
        await session.execute(
            delete(User).where(User.identity.in_([f"{issuer}:{sub}" for sub in subjects]))
        )
        await session.commit()
