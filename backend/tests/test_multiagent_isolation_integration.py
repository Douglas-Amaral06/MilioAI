"""Executes specialist ACL SQL against the isolated PostgreSQL validation database."""

import os
import uuid

import pytest
from sqlalchemy import delete

from app.db.models import Document, DocumentChunk
from app.rag.retrieval import retrieval_query

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DB_TESTS") != "1", reason="Requires isolated migrated PostgreSQL"
    ),
]


async def test_sql_enforces_agent_scope_status_version_contacts_and_local_review(resources):
    app, client, user, other = resources
    settings = app.state.settings
    vector = [1.0] + [0.0] * (settings.embedding_dimensions - 1)
    ids = []
    async with app.state.sessions() as session:
        cases = [
            (
                "allowed",
                "education",
                "approved",
                False,
                "test",
                settings.active_kb_version,
                "Local do curso documentado.",
            ),
            (
                "foreign_domain",
                "rh_frequency",
                "approved",
                False,
                "test",
                settings.active_kb_version,
                "Dado da Frequência.",
            ),
            (
                "pending",
                "education",
                "pending",
                False,
                "test",
                settings.active_kb_version,
                "Documento pendente.",
            ),
            (
                "foreign_contact",
                "education",
                "approved",
                False,
                "test",
                settings.active_kb_version,
                "Telefone 11 97080-6028",
            ),
            (
                "old_version",
                "education",
                "approved",
                False,
                "test",
                "ineligible-old-version",
                "Versão antiga.",
            ),
            (
                "review_only",
                "education",
                "approved",
                True,
                "local_review",
                settings.active_kb_version,
                "Revisão local.",
            ),
            (
                "wrong_scope",
                "education",
                "approved",
                False,
                "private-other-scope",
                settings.active_kb_version,
                "Escopo privado.",
            ),
        ]
        for name, domain, status, review, scope, version, content in cases:
            identifier = uuid.uuid4()
            ids.append(identifier)
            document = Document(
                id=identifier,
                name=name,
                media_type="text/plain",
                domain=domain,
                approved=True,
                status=status,
                validation_only=review,
                scope=scope,
                version=version,
                origin="isolated_multiagent_test",
                storage_key=str(identifier),
                sha256=identifier.hex.ljust(64, "0"),
                embedding_model=settings.embedding_model,
                embedding_dimensions=settings.embedding_dimensions,
                embedding_profile=settings.embedding_profile,
                is_test=True,
            )
            session.add(document)
            await session.flush()
            session.add(
                DocumentChunk(
                    document_id=identifier,
                    content=content,
                    page=1,
                    chunk_index=0,
                    sha256=identifier.hex.ljust(64, "0"),
                    embedding=vector,
                )
            )
        await session.commit()

        def query(config):
            return retrieval_query(
                vector,
                config.model_copy(update={"rag_top_k": 10, "rag_max_distance": 1}),
                ("test", "local_review"),
                "education",
                agent_id="educational_agent",
            )

        rows = (await session.execute(query(settings))).mappings().all()
        names = {row["name"] for row in rows}
        assert names == {"allowed", "review_only"}
        production = settings.model_copy(update={"app_env": "production"})
        rows = (await session.execute(query(production))).mappings().all()
        assert {row["name"] for row in rows} == {"allowed"}
        with pytest.raises(ValueError, match="Unauthorized"):
            retrieval_query(
                vector, settings, ("test",), "rh_frequency", agent_id="educational_agent"
            )
        await session.execute(delete(Document).where(Document.id.in_(ids)))
        await session.commit()
