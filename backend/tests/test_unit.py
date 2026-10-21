import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.rh_frequency import NO_EVIDENCE, route, validate_references
from app.api.schemas import SendInput
from app.core.config import Settings
from app.core.errors import AppError, ModelError
from app.llm.ollama import Ollama
from app.main import create_app
from app.orchestration.graph import build_graph
from app.rag.ingest import chunks
from app.storage.files import validate_file


def config(tmp_path, **changes):
    return Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        app_env="development",
        auth_mode="development",
        dev_auth_token="x" * 32,
        storage_path=tmp_path,
        **changes,
    )


def test_production_cannot_enable_development_auth(tmp_path):
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://unused@localhost/unused",
            app_env="production",
            auth_mode="development",
            dev_auth_token="x" * 32,
        )
    with pytest.raises(ValidationError):
        config(tmp_path, cors_origins=["*"])


def test_input_validation():
    with pytest.raises(ValidationError):
        SendInput(request_id=uuid.uuid4(), content=" ")
    with pytest.raises(ValidationError):
        SendInput(request_id=uuid.uuid4(), content="a" * 4001)


@pytest.mark.parametrize(
    "question",
    [
        "Como envio atestados?",
        "Esqueci o registro de ponto",
        "Justificativa de ausência",
        "Qual a frequência?",
    ],
)
def test_router_rh(question):
    assert route(question, []) == "rh_frequency"


def test_router_unsupported_and_followup():
    assert route("Qual meu vale transporte?", []) == "unavailable"
    assert (
        route("Qual é o prazo?", [{"role": "user", "content": "Como envio um atestado?"}])
        == "rh_frequency"
    )
    assert route("Qual é o prazo?", []) == "unavailable"


def test_file_validation_and_name():
    assert validate_file("../../file.txt", b"test", 1024)[0] == "file.txt"
    for name, data in [("x.exe", b"MZ"), ("x.pdf", b"fake"), ("x.txt", b"\x00")]:
        with pytest.raises(AppError):
            validate_file(name, data, 1024)
    with pytest.raises(AppError) as error:
        validate_file("x.txt", b"x" * 20, 10)
    assert error.value.status == 413
    with pytest.raises(ValueError):
        list(chunks([(None, "a" * 5000)]))


def test_reference_checks():
    cid = str(uuid.uuid4())
    evidence = [{"id": cid, "excerpt": "Teste fictício: 3 dias úteis", "is_test": True}]
    assert validate_references(NO_EVIDENCE, evidence) == []
    assert (
        validate_references(f"Material fictício: 3 dias úteis [fonte:{cid}]", evidence) == evidence
    )
    for answer in [
        "Sem citação",
        f"Material fictício: 10 dias [fonte:{cid}]",
        f"3 dias úteis [fonte:{cid}]",
        f"Material fictício [fonte:{uuid.uuid4()}]",
    ]:
        with pytest.raises(ValueError):
            validate_references(answer, evidence)


async def test_ollama_errors_and_dimensions(tmp_path):
    for transport in [
        httpx.MockTransport(lambda r: httpx.Response(503)),
        httpx.MockTransport(lambda r: httpx.Response(200, json={"embeddings": [[1, 2]]})),
    ]:
        async with httpx.AsyncClient(base_url="http://localhost", transport=transport) as client:
            ollama = Ollama(client, config(tmp_path))
            with pytest.raises(ModelError):
                await ollama.embed(["question"])
    async with httpx.AsyncClient(
        base_url="http://localhost", transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as client:
        with pytest.raises(ModelError):
            async for _ in Ollama(client, config(tmp_path)).chat([]):
                pass


def test_health_and_missing_auth(tmp_path):
    with TestClient(create_app(config(tmp_path))) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        response = client.get("/api/v1/conversations")
        assert response.status_code == 401
        assert "x-request-id" in response.headers
        assert (
            client.get(
                "/api/v1/conversations", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )


async def test_real_graph_no_evidence_and_unsupported(tmp_path, monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("app.orchestration.graph.retrieve", AsyncMock(return_value=[]))
    ollama = AsyncMock()
    ollama.operational_intent.return_value = "documental"
    graph = build_graph(Session, ollama, config(tmp_path))
    initial = {
        "question": "Como envio atestado?",
        "history": [],
        "scopes": ("test",),
        "conversation_id": str(uuid.uuid4()),
    }
    result = await graph.ainvoke(initial)
    assert result["agent"] == "rh_frequency"
    assert result["answer"] == NO_EVIDENCE
    result = await graph.ainvoke({**initial, "question": "Quero informações de vale transporte"})
    assert result["outcome"] == "out_of_scope"
    ollama.chat.assert_not_called()


@pytest.mark.parametrize(
    "change", [{"aud": "wrong"}, {"iss": "https://wrong.example/auth/v1"}, {"exp": 1}]
)
def test_jwt_rejects_invalid_claims(tmp_path, change):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(
        database_url="postgresql+psycopg://unused@localhost/unused",
        app_env="test",
        dev_document_scopes=[],
        auth_mode="jwt",
        jwt_issuer="https://auth.example/auth/v1",
        jwt_jwks_url="https://auth.example/auth/v1/.well-known/jwks.json",
        storage_path=tmp_path,
    )
    app = create_app(settings)

    class Keys:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=key.public_key())

    app.state.jwks = Keys()
    claims = {
        "sub": str(uuid.uuid4()),
        "iss": settings.jwt_issuer,
        "aud": "authenticated",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    claims.update(change)
    with TestClient(app) as client:
        token = jwt.encode(claims, key, algorithm="RS256")
        assert (
            client.get(
                "/api/v1/conversations", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 401
        )
        bad = jwt.encode(
            {**claims, "aud": "authenticated", "iss": settings.jwt_issuer},
            rsa.generate_private_key(public_exponent=65537, key_size=2048),
            algorithm="RS256",
        )
        assert (
            client.get(
                "/api/v1/conversations", headers={"Authorization": "Bearer " + bad}
            ).status_code
            == 401
        )


async def test_database_unavailable_is_controlled(tmp_path):
    settings = config(tmp_path)
    settings.database_url = "postgresql+psycopg://unused@127.0.0.1:9/unused"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/conversations",
                headers={"Authorization": "Bearer " + settings.dev_auth_token},
            )
            assert response.status_code == 503
            assert response.json()["code"] == "database_unavailable"
            assert "password" not in response.text and "Traceback" not in response.text


async def test_scanned_pdf_rejected(tmp_path):
    from pypdf import PdfWriter

    from app.storage.files import extract

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / "scan.pdf"
    with path.open("wb") as output:
        writer.write(output)
    with pytest.raises(AppError) as error:
        await extract(path, "application/pdf")
    assert error.value.code == "pdf_unsupported"
