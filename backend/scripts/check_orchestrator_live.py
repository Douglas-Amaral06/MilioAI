"""Read-only documentary smoke check. No ingestion or document approval changes."""

import asyncio
import json
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.main import create_app

QUESTIONS = [
    "Oi",
    "Bom dia",
    "Obrigado",
    "Qual é o prazo para entregar minha folha ponto?",
    "Oi, como solicito a segunda via do SPTrans?",
    "Qual é o prazo para entregar minha folha ponto? E como solicito a segunda via do meu Bilhete Único SPTrans?",
    "Qual o prazo da Folha Ponto e como solicito a segunda via do SPTrans?",
    "Como solicito a segunda via do SPTrans e quanto custa?",
]


async def main():
    settings = get_settings()
    if settings.app_env != "development":
        raise RuntimeError("Development only")
    app = create_app(settings)
    records = []
    async with app.router.lifespan_context(app):
        for question in QUESTIONS:
            started = time.monotonic()
            state = {
                "conversation_id": "orchestrator-live-smoke",
                "question": question,
                "history": [],
                "scopes": tuple(settings.dev_document_scopes),
                "support_state": {},
                "chunks": [],
                "sources": [],
            }
            result, events = {}, []
            try:
                async with asyncio.timeout(settings.ollama_timeout):
                    async for mode, value in app.state.graph.astream(
                        state, stream_mode=["updates", "custom"]
                    ):
                        if mode == "custom":
                            events.append(value)
                        else:
                            for update in value.values():
                                if update:
                                    result.update(update)
                assert "".join(e.get("text", "") for e in events) == result["answer"]
                source_ids = [s["id"] for s in result.get("sources", [])]
                async with app.state.sessions() as session:
                    domains = (
                        (
                            await session.execute(
                                select(Document.domain)
                                .join(DocumentChunk)
                                .where(DocumentChunk.id.in_(source_ids))
                            )
                        )
                        .scalars()
                        .all()
                        if source_ids
                        else []
                    )
                record = {
                    "question": question,
                    "outcome": result.get("outcome"),
                    "source_ids": [s["id"] for s in result.get("sources", [])],
                    "source_domains": domains,
                    "benefit_codes": [s.get("benefit_code") for s in result.get("sources", [])],
                    "answer": result["answer"],
                    "stream_matches_final": True,
                }
            except Exception as error:
                record = {"question": question, "error": type(error).__name__}
            record["duration_ms"] = round((time.monotonic() - started) * 1000)
            records.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    with open("/tmp/orchestrator-live-results.json", "w") as output:
        json.dump(records, output, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
