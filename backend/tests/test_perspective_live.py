"""Real HTTP/service/model regression for user-directed documentary guidance."""

import os
import uuid

import httpx
import pytest

from app.agents.rh_frequency import normalize
from app.core.config import get_settings
from app.main import create_app

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_PERSPECTIVE_LIVE") != "1",
        reason="Requires local Ollama and approved local-review corpus",
    ),
]


async def test_signing_prohibition_addresses_user():
    settings = get_settings()
    assert settings.app_env == "development" and settings.auth_mode == "development"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + settings.dev_auth_token},
            timeout=settings.ollama_timeout + 10,
        ) as client:
            conversation = await client.post(
                "/api/v1/conversations", json={"title": "Regression perspective FP-09"}
            )
            assert conversation.status_code == 201
            response = await client.post(
                f"/api/v1/conversations/{conversation.json()['id']}/messages",
                json={
                    "request_id": str(uuid.uuid4()),
                    "content": "Posso assinar a folha de outra pessoa ou em branco?",
                },
            )
            assert response.status_code == 201
            message = response.json()
            answer = normalize(message["content"])
            assert message["outcome"] == "answered" and message["sources"]
            assert "nao posso" not in answer
            assert (
                "voce nao pode" in answer
                or "nao e permitido" in answer
                or "nao pode assinar" in answer
            )
            assert "outra pessoa" in answer and "branco" in answer
