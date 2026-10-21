from sqlalchemy import select, true

from app.db.models import Document, DocumentChunk


def retrieval_query(vector, settings, scopes, domain, benefit_code=None):
    authorized = (
        select(
            DocumentChunk.id,
            DocumentChunk.benefit_code,
            DocumentChunk.attributes,
            DocumentChunk.content,
            DocumentChunk.page,
            DocumentChunk.section,
            DocumentChunk.sha256,
            DocumentChunk.chunk_index,
            DocumentChunk.embedding,
            Document.id.label("document_id"),
            Document.name,
            Document.version,
            Document.is_test,
            Document.status,
            Document.validation_only,
        )
        .join(Document)
        .where(
            Document.approved.is_(True),
            Document.status == "approved",
            Document.domain == domain,
            Document.scope.in_(scopes),
            Document.version == settings.active_kb_version,
            Document.embedding_model == settings.embedding_model,
            Document.embedding_dimensions == settings.embedding_dimensions,
            Document.embedding_profile == settings.embedding_profile,
        )
    )
    if benefit_code is not None:
        authorized = authorized.where(DocumentChunk.benefit_code == benefit_code)
    if settings.app_env != "development":
        authorized = authorized.where(Document.validation_only.is_(False))
    corpus = authorized.cte("authorized").prefix_with("MATERIALIZED")
    distance = corpus.c.embedding.cosine_distance(vector)
    return (
        select(corpus, distance.label("distance"))
        .where(true() if benefit_code is not None else distance <= settings.rag_max_distance)
        .order_by(distance, corpus.c.id)
        .limit(settings.rag_top_k)
    )


async def retrieve(session, ollama, settings, question, scopes, domain, benefit_code=None):
    if not scopes:
        return []
    vector = (await ollama.embed([question], query=True))[0]
    rows = (
        (await session.execute(retrieval_query(vector, settings, scopes, domain, benefit_code)))
        .mappings()
        .all()
    )
    return [
        {
            "id": str(r["id"]),
            "benefit_code": r["benefit_code"],
            "attributes": r["attributes"],
            "document_id": str(r["document_id"]),
            "title": r["name"],
            "version": r["version"],
            "page": r["page"],
            "section": r["section"],
            "sha256": r["sha256"],
            "chunk": r["chunk_index"],
            "excerpt": r["content"],
            "is_test": r["is_test"],
            "validation_only": r["validation_only"],
            "score": round(1 - float(r["distance"]), 6),
            "status": r["status"],
        }
        for r in rows
    ]
