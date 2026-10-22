"""Bounded live checks of changed routes. No historical metrics are overwritten."""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.db.session import database
from app.llm.ollama import Ollama
from app.orchestration.graph import build_graph


async def main():
    settings = get_settings()
    assert "milioai_multiagent_" in settings.database_url, "Use an isolated validation database"
    engine, sessions = database(settings.database_url)
    scenarios = [
        (
            "generate_timesheet",
            "Onde gero minha Folha Ponto?",
            "E onde gero mesmo?",
            "folha_ponto",
            "frequency_agent",
        ),
        (
            "course_certificate",
            "Como envio um atestado de falta no curso?",
            "Onde envio o atestado do curso mesmo?",
            "falta_curso",
            "educational_agent",
        ),
        (
            "work_certificate",
            "Onde entrego um atestado de falta no trabalho?",
            "E onde envio esse atestado do trabalho?",
            "falta_trabalho",
            "frequency_agent",
        ),
        (
            "benefit_discount",
            "Quem é responsável pelo desconto indevido no VT?",
            "Com quem falo sobre o desconto no VT?",
            "vale_transporte",
            "service_agent",
        ),
        (
            "sptrans",
            "Como solicito a segunda via do SPTrans?",
            "Quanto custa a segunda via do SPTrans?",
            "vale_transporte",
            "service_agent",
        ),
        (
            "instructor",
            "Com quem falo sobre meu instrutor?",
            "Não sei quem é meu instrutor.",
            "falta_curso",
            "educational_agent",
        ),
    ]
    if "--scenario" in sys.argv:
        wanted = sys.argv[sys.argv.index("--scenario") + 1]
        scenarios = [s for s in scenarios if s[0] == wanted]
    results = []
    async with httpx.AsyncClient(
        base_url=settings.ollama_url, timeout=settings.ollama_timeout, trust_env=False
    ) as client:
        tags = await client.get("/api/tags")
        tags.raise_for_status()
        model = Ollama(client, settings)
        graph = build_graph(sessions, model, settings)
        for name, first, second, topic, expected in scenarios:
            history = []
            flow = {}
            for turn, question in enumerate((first, second), 1):
                started = time.monotonic()
                try:
                    async with asyncio.timeout(settings.ollama_timeout):
                        result = await graph.ainvoke(
                            {
                                "conversation_id": "multiagent-live-" + name,
                                "question": question,
                                "topic_id": topic,
                                "question_id": None,
                                "history": history,
                                "scopes": ("local_review", "education:contacts"),
                                "support_state": flow,
                                "chunks": [],
                                "sources": [],
                                "contacts": [],
                            }
                        )
                    row = {
                        "scenario": name,
                        "turn": turn,
                        "question": question,
                        "agent": result.get("agent"),
                        "expected_agent": expected,
                        "route_pass": result.get("agent") == expected,
                        "answer": result.get("answer"),
                        "outcome": result.get("outcome"),
                        "generation_mode": result.get("generation_mode", "deterministic"),
                        "sources": result.get("sources", []),
                        "contacts": result.get("contacts", []),
                    }
                    history += [
                        {"role": "user", "content": question, "topic_id": topic},
                        {"role": "assistant", "content": result["answer"], "topic_id": topic},
                    ]
                    flow = result.get("support_state", {})
                except Exception as error:
                    row = {
                        "scenario": name,
                        "turn": turn,
                        "question": question,
                        "error": type(error).__name__,
                        "route_pass": False,
                    }
                row["latency_ms"] = round((time.monotonic() - started) * 1000)
                results.append(row)
                Path("multiagent-live.json").write_text(
                    json.dumps(
                        {"model": settings.ollama_model, "results": results},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(
                    json.dumps(
                        {
                            k: v
                            for k, v in row.items()
                            if k not in {"answer", "sources", "contacts"}
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    await engine.dispose()


asyncio.run(main())
