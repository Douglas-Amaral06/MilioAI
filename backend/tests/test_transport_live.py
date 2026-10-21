import os
import uuid
from argparse import Namespace
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.main import create_app
from app.rag.retrieval import retrieve
from app.rag.transport_extract import DOMAIN, EXPECTED_CODES, extract_rows
from app.rag.transport_ingest import ingest, transport_settings

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_TRANSPORT_LIVE") != "1",
        reason="Requires reviewed VT PDF, local Ollama and PostgreSQL",
    ),
]
SOURCE = Path(os.getenv("VT_SOURCE_PATH", "/input/vt.pdf"))


async def test_exact_33_extraction_and_idempotent_reindex():
    rows = extract_rows(SOURCE)
    assert len(rows) == 33 and {r["code"] for r in rows} == EXPECTED_CODES
    assert sum(r["page"] == 1 for r in rows) == 24
    assert "01 dia útil" in next(r for r in rows if r["code"] == "216")["procedure"]
    settings = get_settings()
    app = create_app(settings)
    async with app.router.lifespan_context(app):

        async def counts():
            async with app.state.sessions() as session:
                return (
                    await session.execute(
                        select(
                            func.count(DocumentChunk.id),
                            func.count(func.distinct(DocumentChunk.benefit_code)),
                        )
                        .join(Document)
                        .where(
                            Document.domain == DOMAIN, Document.version == settings.vt_kb_version
                        )
                    )
                ).one()

        assert await counts() == (33, 33)
        await ingest(
            Namespace(
                path=SOURCE,
                approve=True,
                local_review=True,
                scope="local_review",
                display_name=SOURCE.name,
            )
        )
        assert await counts() == (33, 33)
        async with app.state.sessions() as session:
            for row in rows:
                found = await retrieve(
                    session,
                    app.state.ollama,
                    transport_settings(settings),
                    f"Segunda via {row['name']}",
                    ("local_review",),
                    DOMAIN,
                    benefit_code=row["code"],
                )
                assert len(found) == 1 and found[0]["benefit_code"] == row["code"]
                assert found[0]["attributes"]["procedure"] == row["procedure"]
                assert found[0]["attributes"]["fee"] == row["fee"]
            assert (
                await retrieve(
                    session,
                    app.state.ollama,
                    transport_settings(settings),
                    "SPTrans",
                    (),
                    DOMAIN,
                    benefit_code="89",
                )
                == []
            )
            assert (
                await retrieve(
                    session,
                    app.state.ollama,
                    transport_settings(settings),
                    "SPTrans",
                    ("local_review",),
                    DOMAIN,
                    benefit_code="999999",
                )
                == []
            )


async def test_real_api_cards_followup_invalid_change_and_sources():
    settings = get_settings()
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + settings.dev_auth_token},
        ) as client:
            assert len((await client.get("/api/v1/support/transport-cards")).json()) == 33
            cid = (
                await client.post("/api/v1/conversations", json={"title": "VT validation"})
            ).json()["id"]

            async def send(**payload):
                return await client.post(
                    f"/api/v1/conversations/{cid}/messages",
                    json={"request_id": str(uuid.uuid4()), **payload},
                )

            try:
                first = await send(content="Perdi meu vale-transporte.")
                assert (
                    first.status_code == 201
                    and first.json()["content"] == "Claro! Qual cartão de transporte você utiliza?"
                )
                assert (
                    await send(action={"kind": "card_select", "benefit_code": "999999"})
                ).status_code == 422
                for code, fee, term in [
                    ("89", "7 tarifas", "72 horas"),
                    ("9156", "R$ 28,50", "autoatendimento"),
                    ("503", "5 tarifas", "sac@soudiadema.com.br"),
                    ("182", "R$ 40,80", "Empresa"),
                    ("216", "R$ 5,74", "01 dia útil"),
                ]:
                    if code != "89":
                        assert (await send(action={"kind": "card_change"})).status_code == 201
                    result = await send(action={"kind": "card_select", "benefit_code": code})
                    assert result.status_code == 201, result.text
                    answer = result.json()
                    assert fee in answer["content"] and term in answer["content"]
                    assert (
                        len(answer["sources"]) == 1 and answer["sources"][0]["benefit_code"] == code
                    )
                    assert answer["sources"][0]["page"] in [1, 2]
                    state = (await client.get(f"/api/v1/conversations/{cid}")).json()[
                        "support_state"
                    ]
                    assert state["selected_card_code"] == code
                result = await send(content="E quanto custa?")
                assert result.status_code == 201 and "R$ 5,74" in result.json()["content"]
                assert result.json()["sources"][0]["benefit_code"] == "216"
                result = await send(content="Meu cartão é SPTrans.")
                assert "7 tarifas" in result.json()["content"]
                await send(content="BB Turismo")
                assert (await client.get(f"/api/v1/conversations/{cid}")).json()["support_state"][
                    "vt_stage"
                ] == "selection"
                result = await send(content="Sancetur Valinhos")
                assert result.json()["sources"][0]["benefit_code"] == "3845"
                await send(content="Meu cartão é SPTrans.")
                result = await send(content="Qual o prazo de retirada?")
                assert "72 horas" in result.json()["content"]
                assert result.json()["sources"][0]["benefit_code"] == "89"
                await send(content="Meu cartão é Inexistente.")
                assert (await client.get(f"/api/v1/conversations/{cid}")).json()["support_state"][
                    "vt_stage"
                ] == "selection"
                result = await send(content="Onde baixo meu holerite?")
                assert "Conecta Jovem" in result.json()["content"]
                assert (await client.get(f"/api/v1/conversations/{cid}")).json()["support_state"][
                    "vt_stage"
                ] == "idle"
            finally:
                await client.delete(f"/api/v1/conversations/{cid}")
