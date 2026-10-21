import os
import uuid

import httpx
import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.errors import ModelError
from app.db.models import Conversation
from app.llm.ollama import Ollama
from app.main import create_app

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_TESTS") != "1", reason="Set RUN_LIVE_TESTS=1 for actual local Ollama"
    ),
]


async def test_real_ollama_rag_and_persistence():
    settings = get_settings().model_copy(
        update={"active_kb_version": "test-v1", "rag_profile": "legacy"}
    )
    assert settings.auth_mode == "development", (
        "Live acceptance uses an explicit isolated local identity"
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        headers = {"Authorization": "Bearer " + settings.dev_auth_token}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
        ) as client:
            response = await client.post(
                "/api/v1/conversations", json={"title": "Live acceptance test"}
            )
            assert response.status_code == 201, response.text
            cid = response.json()["id"]
            try:
                response = await client.post(
                    f"/api/v1/conversations/{cid}/messages",
                    json={
                        "request_id": str(uuid.uuid4()),
                        "content": "No documento fictício de teste, qual o prazo para enviar um atestado após o retorno?",
                    },
                )
                assert response.status_code == 201, response.text
                message = response.json()
                assert message["role"] == "assistant" and message["status"] == "complete"
                assert "3" in message["content"] and message["sources"]
                assert all(source["is_test"] for source in message["sources"])
                assert (
                    "let's" not in message["content"].lower()
                    and "<think>" not in message["content"]
                )
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
                ) as reloaded:
                    history = (await reloaded.get(f"/api/v1/conversations/{cid}/messages")).json()
                    assert history[-1]["id"] == message["id"]
            finally:
                async with app.state.sessions() as session:
                    await session.execute(
                        delete(Conversation).where(Conversation.id == uuid.UUID(cid))
                    )
                    await session.commit()


async def test_real_model_connection_failure():
    settings = get_settings()
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:9", timeout=2, trust_env=False
    ) as client:
        with pytest.raises(ModelError):
            await Ollama(client, settings).embed(["Teste de indisponibilidade"])
