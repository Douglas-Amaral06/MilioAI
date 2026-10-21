"""Administrative, idempotent ingestion of the reviewed 33-card source."""

import argparse
import asyncio
import hashlib
from pathlib import Path

import httpx
from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import database
from app.llm.ollama import Ollama
from app.rag.transport_extract import DOMAIN, extract_rows, record_hash, record_text
from app.storage.files import PrivateStorage, validate_file


def transport_settings(settings):
    return settings.model_copy(
        update={"active_kb_version": settings.vt_kb_version, "rag_profile": "vt-table-v1"}
    )


async def ingest(args):
    settings = transport_settings(get_settings())
    if not args.approve or not args.local_review or settings.app_env != "development":
        raise SystemExit("This unconfirmed source requires --approve --local-review in development")
    data = args.path.read_bytes()
    name, media_type = validate_file(args.path.name, data, settings.upload_max_bytes)
    digest = hashlib.sha256(data).hexdigest()
    rows = extract_rows(args.path)
    storage = PrivateStorage(settings.storage_path)
    engine, sessions = database(settings.database_url)
    key = None
    try:
        async with sessions() as session:
            # Serialize concurrent reindexing of this exact space as well as enforcing DB uniqueness.
            lock_key = int.from_bytes(
                hashlib.sha256(
                    f"{digest}:{settings.active_kb_version}:{args.scope}:{settings.embedding_profile}".encode()
                ).digest()[:8],
                "big",
                signed=True,
            )
            await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
            existing = await session.scalar(
                select(Document).where(
                    Document.sha256 == digest,
                    Document.version == settings.active_kb_version,
                    Document.scope == args.scope,
                    Document.embedding_model == settings.embedding_model,
                    Document.embedding_dimensions == settings.embedding_dimensions,
                    Document.embedding_profile == settings.embedding_profile,
                )
            )
            if existing:
                print(f"Already indexed: {existing.id}; 33 cards; no embeddings regenerated")
                return
            key = storage.put(data)
            async with httpx.AsyncClient(
                base_url=settings.ollama_url, timeout=settings.ollama_timeout, trust_env=False
            ) as client:
                model = Ollama(client, settings)
                vectors = []
                for start in range(0, len(rows), 8):
                    vectors.extend(
                        await model.embed(
                            [
                                f"Segunda via de vale-transporte. {record_text(row)}"
                                for row in rows[start : start + 8]
                            ]
                        )
                    )
            doc = Document(
                name=args.display_name,
                media_type=media_type,
                domain=DOMAIN,
                approved=True,
                status="approved",
                validation_only=True,
                embedding_profile=settings.embedding_profile,
                version=settings.active_kb_version,
                scope=args.scope,
                origin="administrative_cli:vt-table-v1",
                storage_key=key,
                sha256=digest,
                embedding_model=settings.embedding_model,
                embedding_dimensions=settings.embedding_dimensions,
                is_test=False,
            )
            session.add(doc)
            await session.flush()
            for index, (row, vector) in enumerate(zip(rows, vectors, strict=True)):
                session.add(
                    DocumentChunk(
                        document_id=doc.id,
                        benefit_code=row["code"],
                        attributes=row,
                        content=record_text(row),
                        page=row["page"],
                        section=f"{row['code']} · {row['name']}",
                        sha256=record_hash(row),
                        chunk_index=index,
                        embedding=vector,
                    )
                )
            await session.commit()
            key = None
            print(
                f"Indexed {doc.id}: 33 chunks; {settings.embedding_model}; {settings.embedding_dimensions} dimensions; pages 1/2"
            )
    finally:
        if key:
            storage.remove(key)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index the reviewed two-page VT card table")
    parser.add_argument("path", type=Path)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--local-review", action="store_true")
    parser.add_argument("--scope", required=True)
    parser.add_argument("--display-name", default="orientações segunda via cartões vt (1).pdf")
    asyncio.run(ingest(parser.parse_args()))
