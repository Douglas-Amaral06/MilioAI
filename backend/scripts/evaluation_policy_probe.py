"""Read-only SQL diagnostics; not an authentication or production deployment test."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import database
from app.rag.evaluate_real import PolicySettings
from app.rag.retrieval import retrieval_query
from app.support.transport import catalog_query


async def main(output):
    settings = get_settings()
    assert settings.app_env == "development"
    engine, sessions = database(settings.database_url)
    result = {
        "kind": "supplementary_read_only_policy_probe",
        "production_deployment_test": False,
        "model_calls": 0,
    }
    try:
        async with sessions() as session:
            vector = await session.scalar(
                select(DocumentChunk.embedding)
                .join(Document)
                .where(
                    Document.domain == "rh_frequency",
                    Document.version == settings.active_kb_version,
                )
                .limit(1)
            )
            assert vector is not None
            frequency = (
                await session.execute(
                    retrieval_query(
                        vector, PolicySettings(settings), ("local_review",), "rh_frequency"
                    )
                )
            ).all()
            transport_production = (
                await session.execute(catalog_query(PolicySettings(settings), ("local_review",)))
            ).all()
            transport_dev = (
                await session.execute(catalog_query(settings, ("local_review",)))
            ).all()
            no_scope = (await session.execute(catalog_query(settings, ()))).all()
            result.update(
                frequency_production_filtered_rows=len(frequency),
                transport_production_filtered_rows=len(transport_production),
                transport_development_rows=len(transport_dev),
                transport_without_scope_rows=len(no_scope),
            )
            assert not frequency and not transport_production and not no_scope
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(main(parser.parse_args().output))
