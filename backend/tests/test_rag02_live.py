import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.main import create_app

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_RAG02_LIVE") != "1",
        reason="Requires supplied PDF corpus, PostgreSQL and Ollama",
    ),
]
CASES = [
    ("prazo", "folha_ponto", "folha_ponto.prazo", None, "2.", 1, r"segundo|2"),
    (
        "horarios",
        "folha_ponto",
        "folha_ponto.horarios",
        None,
        "3.",
        1,
        r"brit[aâ]nico|hor[aá]rios corretos",
    ),
    ("curso", "falta_curso", "falta_curso.registro", None, "3.", 1, r"CURSO"),
    ("assinaturas", "outros", None, "Quem precisa assinar minha folha?", "5.", 2, r"aprendiz"),
    ("vt", "vale_transporte", "vale_transporte.credito", None, None, None, None),
    ("salario", "salario", "salario.data", None, None, None, None),
    ("ferias", "outros", None, "Como solicito minhas férias?", None, None, None),
    ("atestados", "atestados", "atestados.prazo", None, None, None, None),
]


@pytest.mark.parametrize("key,topic,qid,text,section,page,expected", CASES)
async def test_supplied_document_answers(key, topic, qid, text, section, page, expected):
    settings = get_settings()
    assert settings.active_kb_version == "folha-ponto-local-v1"
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer " + settings.dev_auth_token},
        ) as client:
            cid = (
                await client.post("/api/v1/conversations", json={"title": "RAG02 live: " + key})
            ).json()["id"]
            try:
                result = await client.post(
                    f"/api/v1/conversations/{cid}/messages",
                    json={
                        "request_id": str(uuid.uuid4()),
                        "topic_id": topic,
                        "question_id": qid,
                        "content": text,
                    },
                )
                message = result.json()
                folder = os.getenv("RAG02_REPORT_DIR")
                if folder:
                    Path(folder).mkdir(parents=True, exist_ok=True)
                    Path(folder, f"{key}.json").write_text(
                        json.dumps(
                            {
                                "status": result.status_code,
                                "response": {
                                    **message,
                                    "sources": [
                                        {k: v for k, v in source.items() if k != "excerpt"}
                                        for source in message.get("sources", [])
                                    ],
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                assert result.status_code == 201, result.text
                if section:
                    assert message["outcome"] in {"answered", "partial"}, message
                    assert re.search(expected, message["content"], re.I), message
                    assert any(
                        s["section"].startswith(section) and s["page"] == page
                        for s in message["sources"]
                    ), message
                    assert all(s["validation_only"] for s in message["sources"])
                    if key == "curso":
                        assert not re.search(r"campo.{0,15}falta", message["content"], re.I), (
                            message
                        )
                elif key == "atestados":
                    assert re.search(
                        r"n[aã]o (encontrei|informa|especific|h[aá]|encontr|fornec|menciona)|sem informa",
                        message["content"],
                        re.I,
                    ), message
                    assert "3 dias" not in message["content"]
                else:
                    assert message["outcome"] == "out_of_scope" and message["sources"] == []
                if key == "prazo":
                    follow = await client.post(
                        f"/api/v1/conversations/{cid}/messages",
                        json={"request_id": str(uuid.uuid4()), "content": "E se eu atrasar?"},
                    )
                    value = follow.json()
                    if folder:
                        Path(folder, "continuidade.json").write_text(
                            json.dumps(
                                {
                                    "status": follow.status_code,
                                    "response": {
                                        **value,
                                        "sources": [
                                            {k: v for k, v in source.items() if k != "excerpt"}
                                            for source in value.get("sources", [])
                                        ],
                                    },
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                    assert follow.status_code == 201, follow.text
                    assert re.search(r"pode|podem|poder|poss[ií]v", value["content"], re.I), value
                    assert any(s["section"].startswith("2.") for s in value["sources"])
                    await client.patch(
                        f"/api/v1/conversations/{cid}/topic", json={"topic_id": "vale_transporte"}
                    )
                    switched = (
                        await client.post(
                            f"/api/v1/conversations/{cid}/messages",
                            json={
                                "request_id": str(uuid.uuid4()),
                                "topic_id": "vale_transporte",
                                "question_id": "vale_transporte.credito",
                            },
                        )
                    ).json()
                    assert switched["outcome"] == "out_of_scope" and switched["sources"] == []
                reloaded = (await client.get(f"/api/v1/conversations/{cid}/messages")).json()
                assert any(m["id"] == message["id"] for m in reloaded)
            finally:
                await client.delete(f"/api/v1/conversations/{cid}")
