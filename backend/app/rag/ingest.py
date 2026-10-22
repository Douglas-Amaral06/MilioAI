import argparse
import asyncio
import hashlib
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import database
from app.llm.ollama import Ollama
from app.rag.chunking import semantic_chunks
from app.storage.files import PrivateStorage, extract, validate_file


def chunks(pages):
    # Kept as a small compatibility adapter for existing callers; source-aware ingestion uses full metadata.
    for item in semantic_chunks(pages):
        yield item.page, item.content


async def ingest(args):
    settings = get_settings()
    from app.agents.policies import specialist_settings

    agent_id = {
        "education": "educational_agent",
        "rh_frequency": "frequency_agent",
        "benefits": "service_agent",
    }[getattr(args, "domain", "rh_frequency")]
    settings = specialist_settings(settings, agent_id)
    if not args.approve:
        raise SystemExit("Explicit --approve is required for administrative indexing")
    if args.test and args.scope != "test":
        raise SystemExit("Test material must use the isolated test scope")
    local_review = getattr(args, "local_review", False)
    if local_review and settings.app_env != "development":
        raise SystemExit("Local review corpus is restricted to development")
    data = args.path.read_bytes()
    name, media_type = validate_file(args.path.name, data, settings.upload_max_bytes)
    digest = hashlib.sha256(data).hexdigest()
    storage = PrivateStorage(settings.storage_path)
    engine, sessions = database(settings.database_url)
    key = None
    try:
        async with sessions() as session:
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
                if existing.domain != getattr(args, "domain", "rh_frequency"):
                    raise ValueError(
                        "Existing source belongs to a different domain; review classification and version explicitly"
                    )
                if getattr(args, "display_name", None):
                    existing.name = args.display_name[:255]
                    await session.commit()
                print(f"Already indexed: {existing.id}")
                return
            key = storage.put(data)
            extracted = list(semantic_chunks(await extract(storage.path(key), media_type)))
            if not extracted or len(extracted) > 400:
                raise ValueError("Empty or oversized corpus")
            async with httpx.AsyncClient(
                base_url=settings.ollama_url, timeout=settings.ollama_timeout, trust_env=False
            ) as client:
                ollama = Ollama(client, settings)
                vectors = []
                for start in range(0, len(extracted), 8):
                    vectors.extend(
                        await ollama.embed(
                            [
                                f"Documento: {name}. Seção: {item.section}.\n{item.content}"
                                for item in extracted[start : start + 8]
                            ]
                        )
                    )
            document = Document(
                name=(getattr(args, "display_name", None) or name)[:255],
                media_type=media_type,
                domain=getattr(args, "domain", "rh_frequency"),
                approved=True,
                status="approved",
                validation_only=local_review,
                embedding_profile=settings.embedding_profile,
                version=settings.active_kb_version,
                scope=args.scope,
                origin="administrative_cli",
                storage_key=key,
                sha256=digest,
                embedding_model=settings.embedding_model,
                embedding_dimensions=settings.embedding_dimensions,
                is_test=args.test,
            )
            session.add(document)
            await session.flush()
            for index, (item, vector) in enumerate(zip(extracted, vectors, strict=True)):
                session.add(
                    DocumentChunk(
                        document_id=document.id,
                        content=item.content,
                        page=item.page,
                        section=item.section,
                        sha256=item.sha256,
                        chunk_index=index,
                        embedding=vector,
                    )
                )
            await session.commit()
            print(
                f"Indexed {document.id}: {len(extracted)} chunks; {settings.embedding_dimensions} dimensions"
            )
            key = None
    finally:
        if key:
            storage.remove(key)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Administrative approved corpus ingestion; never exposed as an HTTP endpoint"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--scope", required=True)
    parser.add_argument(
        "--domain", choices=["rh_frequency", "education", "benefits"], default="rh_frequency"
    )
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--display-name", help="Original document name for source attribution")
    parser.add_argument(
        "--local-review",
        action="store_true",
        help="Restrict this corpus to development; institutional validity is unconfirmed",
    )
    asyncio.run(ingest(parser.parse_args()))
