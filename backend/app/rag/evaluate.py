"""Small, explicit retrieval evaluation against the supplied PDF; no user queries are stored."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.db.session import database
from app.llm.ollama import Ollama
from app.rag.retrieval import retrieve

CASES = [
    ("prazo", "Folha Ponto: Qual é o prazo de entrega da folha ponto?", {"2."}, 1),
    ("horarios", "Folha Ponto: Posso preencher sempre com o mesmo horário?", {"3."}, 1),
    ("curso", "Falta no Curso: Como registrar uma falta no dia de curso?", {"3."}, 1),
    ("assinaturas", "Quem precisa assinar minha folha?", {"5."}, 2),
    ("envio", "Folha Ponto: Onde devo enviar minha folha ponto?", {"6."}, 2),
    (
        "atraso",
        "Folha Ponto: E se eu atrasar? Contexto: Qual é o prazo de entrega da folha ponto?",
        {"2."},
        1,
    ),
]


async def evaluate(output):
    settings = get_settings()
    engine, sessions = database(settings.database_url)
    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_url, timeout=settings.ollama_timeout, trust_env=False
        ) as client:
            ollama = Ollama(client, settings)
            async with sessions() as session:
                for key, question, expected, page in CASES:
                    rows = await retrieve(
                        session, ollama, settings, question, ("local_review",), "rh_frequency"
                    )
                    ranks = [
                        i + 1
                        for i, r in enumerate(rows)
                        if any(r["section"].startswith(s) for s in expected) and r["page"] == page
                    ]
                    matched = {
                        s
                        for s in expected
                        if any(r["section"].startswith(s) and r["page"] == page for r in rows)
                    }
                    results.append(
                        {
                            "case": key,
                            "hit": bool(ranks),
                            "recall": len(matched) / len(expected),
                            "reciprocal_rank": 1 / min(ranks) if ranks else 0,
                            "expected_page": page,
                            "candidates": [
                                {k: r[k] for k in ["id", "document_id", "section", "page", "score"]}
                                for r in rows
                            ],
                        }
                    )
        report = {
            "sample_size": len(results),
            "top_k": settings.rag_top_k,
            "hit_rate_at_k": sum(r["hit"] for r in results) / len(results),
            "recall_at_k": sum(r["recall"] for r in results) / len(results),
            "mrr_at_k": sum(r["reciprocal_rank"] for r in results) / len(results),
            "cases": results,
            "limitation": "Six curated questions from one local-review PDF; this is not an estimate of general accuracy.",
        }
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    asyncio.run(evaluate(parser.parse_args().output))
