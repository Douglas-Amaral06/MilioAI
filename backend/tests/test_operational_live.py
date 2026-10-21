import os
import uuid

import httpx
import pytest

from app.core.config import get_settings
from app.main import create_app
from app.support.operational import CONFIG, detect

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_OPERATIONAL_LIVE") != "1", reason="Requires real local Ollama and PostgreSQL"
    ),
]
CASES = [
    ("Onde gero minha folha?", "generate_timesheet"),
    ("Quero baixar minha folha de frequência", "generate_timesheet"),
    ("Onde vejo meus dias de curso?", "calendar"),
    ("Como descubro quando tiro férias?", "vacation"),
    ("Onde baixo meu contracheque?", "payslip"),
    ("Onde mando minha declaração da escola?", "school_documents"),
    ("Faltei na capacitação. Onde mando meu atestado?", "course_certificate"),
    ("Onde envio minha folha ponto assinada?", "send_timesheet"),
    ("Como justifico minha falta no trabalho?", "work_certificate"),
    ("Preciso entregar meu documento.", "ambiguous_document"),
    ("Como solicito minhas férias?", "documental"),
    ("Qual é o prazo de entrega da folha ponto?", "documental"),
    ("Como descubro quem é meu instrutor?", "course_contact"),
    ("Como entro em contato com o educacional?", "education_contact"),
    ("preciso pegar o papel do ponto pra preencher, onde acho?", "generate_timesheet"),
]


@pytest.mark.parametrize("question,intent", CASES)
async def test_real_semantic_intents(question, intent):
    app = create_app(get_settings())
    async with app.router.lifespan_context(app):
        actual = await detect(app.state.ollama, question, None, "outros", [], {})
        assert actual == intent, f"{question}: {actual} != {intent}"


async def test_real_api_instructor_and_rag():
    settings = get_settings()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + settings.dev_auth_token},
        ) as client:
            cid = (
                await client.post("/api/v1/conversations", json={"title": "Validação operacional"})
            ).json()["id"]

            async def send(**payload):
                response = await client.post(
                    f"/api/v1/conversations/{cid}/messages",
                    json={"request_id": str(uuid.uuid4()), **payload},
                )
                assert response.status_code == 201, response.text
                return response.json()

            try:
                answer = await send(content="Faltei na capacitação. Onde mando meu atestado?")
                assert (
                    CONFIG["portal_url"] in answer["content"]
                    and "Você sabe quem é" in answer["content"]
                )
                await send(content="Sim.")
                answer = await send(
                    action={"kind": "instructor_select", "instructor_id": "instructor-03"}
                )
                assert "vinicius.maia@renapsi.org.br" in answer["content"]
                await send(action={"kind": "instructor_resume"})
                answer = await send(content="Onde baixo meu holerite?")
                assert "holerite" in answer["content"] and CONFIG["portal_url"] in answer["content"]
                answer = await send(content="Preciso entregar meu documento.")
                assert "Qual documento" in answer["content"]
                answer = await send(content="Qual o prazo da folha ponto?")
                assert answer["sources"] and any(
                    "2." in item["section"] for item in answer["sources"]
                )
                assert "segundo" in answer["content"].lower() or "2" in answer["content"]
            finally:
                await client.delete(f"/api/v1/conversations/{cid}")
