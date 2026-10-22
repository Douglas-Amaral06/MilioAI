import math
import re
from collections import Counter

from sqlalchemy import select, true

from app.agents.rh_frequency import normalize
from app.db.models import Document, DocumentChunk


def authorized_corpus(settings, scopes, domain, benefit_code=None, *, agent_id=None):
    if agent_id is not None:
        from app.agents.policies import authorize_tool

        authorize_tool(agent_id, "documents", domain)
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
    if agent_id is not None:
        from app.agents.policies import SPECIALISTS
        from app.support.contacts import CONTACTS

        authorized = authorized.where(
            Document.media_type.in_(("application/pdf", "text/plain", "text/markdown"))
        )
        for contact in CONTACTS.values():
            if contact["owner_domain"] != SPECIALISTS[agent_id].domain:
                for value in (
                    contact["phone"].removeprefix("+55 "),
                    contact["phone_digits"],
                    contact["email"],
                ):
                    authorized = authorized.where(~DocumentChunk.content.contains(value))
    if benefit_code is not None:
        authorized = authorized.where(DocumentChunk.benefit_code == benefit_code)
    if settings.app_env != "development":
        authorized = authorized.where(
            Document.validation_only.is_(False), Document.scope != "local_review"
        )
    return authorized.cte("authorized").prefix_with("MATERIALIZED")


def retrieval_query(vector, settings, scopes, domain, benefit_code=None, *, agent_id=None):
    corpus = authorized_corpus(settings, scopes, domain, benefit_code, agent_id=agent_id)
    distance = corpus.c.embedding.cosine_distance(vector)
    return (
        select(corpus, distance.label("distance"))
        .where(true() if benefit_code is not None else distance <= settings.rag_max_distance)
        .order_by(distance, corpus.c.id)
        .limit(settings.rag_top_k)
    )


def lexical_rank(question, rows):
    stop = set(
        "a o os as de do da dos das em no na para por e um uma eu meu minha como qual quais posso pode preciso devo folha ponto".split()
    )

    def terms(text):
        return [
            t.rstrip("s")
            for t in re.findall(r"[a-z0-9]+", normalize(text))
            if len(t) > 2 and t not in stop
        ]

    query = set(terms(question))
    counts = [Counter(terms(row["content"])) for row in rows]
    frequencies = Counter(t for count in counts for t in count)
    scored = []
    average = sum(sum(c.values()) for c in counts) / max(len(counts), 1)
    for row, count in zip(rows, counts, strict=True):
        score = sum(
            math.log(1 + (len(rows) - frequencies[t] + 0.5) / (frequencies[t] + 0.5))
            * count[t]
            * 2.2
            / (count[t] + 1.2 * (0.25 + 0.75 * sum(count.values()) / max(average, 1)))
            for t in query
            if count[t]
        )
        if score > 0:
            scored.append((score, row))
    return [row for _, row in sorted(scored, key=lambda pair: (-pair[0], str(pair[1]["id"])))]


async def retrieve(
    session, ollama, settings, question, scopes, domain, benefit_code=None, *, agent_id=None
):
    from app.agents.policies import authorize_tool

    if agent_id is not None:
        authorize_tool(agent_id, "documents", domain)
    if not scopes:
        return []
    vector = (await ollama.embed([question], query=True))[0]
    rows = (
        (
            await session.execute(
                retrieval_query(vector, settings, scopes, domain, benefit_code, agent_id=agent_id)
            )
        )
        .mappings()
        .all()
    )
    if domain == "rh_frequency" and benefit_code is None:
        corpus = authorized_corpus(settings, scopes, domain, agent_id=agent_id)
        candidates = (
            (
                await session.execute(
                    select(corpus, corpus.c.embedding.cosine_distance(vector).label("distance"))
                )
            )
            .mappings()
            .all()
        )
        lexical = lexical_rank(question, candidates)
        combined = {str(row["id"]): row for row in [*rows, *lexical]}
        scores = Counter()
        for weight, ranking in [(1, rows), (2, lexical)]:
            for rank, row in enumerate(ranking, 1):
                scores[str(row["id"])] += weight / (60 + rank)
        rows = [
            combined[key]
            for key in sorted(scores, key=lambda key: (-scores[key], key))[: settings.rag_top_k]
        ]
    if agent_id is not None:
        from app.agents.policies import SPECIALISTS
        from app.support.contacts import CONTACTS
        from app.support.exact import EMAIL, PHONE, phone_key

        policy = SPECIALISTS[agent_id]
        foreign = [c for c in CONTACTS.values() if c["owner_domain"] != policy.domain]

        def safe(row):
            phones = {phone_key(m.group()) for m in PHONE.finditer(row["content"])}
            emails = {m.group() for m in EMAIL.finditer(row["content"])}
            return not any(phone_key(c["phone"]) in phones or c["email"] in emails for c in foreign)

        rows = [r for r in rows if safe(r)]
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
