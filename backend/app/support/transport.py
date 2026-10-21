"""Authorized card directory and source-exact transport guidance."""

import re

from sqlalchemy import select

from app.agents.rh_frequency import normalize
from app.core.errors import AppError
from app.db.models import Document, DocumentChunk
from app.rag.transport_extract import DOMAIN
from app.rag.transport_ingest import transport_settings


def catalog_query(settings, scopes):
    config = transport_settings(settings)
    query = (
        select(DocumentChunk.benefit_code, DocumentChunk.attributes)
        .join(Document)
        .where(
            Document.domain == DOMAIN,
            Document.approved.is_(True),
            Document.status == "approved",
            Document.scope.in_(scopes),
            Document.version == config.active_kb_version,
            Document.embedding_model == config.embedding_model,
            Document.embedding_dimensions == config.embedding_dimensions,
            Document.embedding_profile == config.embedding_profile,
            DocumentChunk.benefit_code.is_not(None),
        )
    )
    if settings.app_env != "development":
        query = query.where(Document.validation_only.is_(False))
    return query


async def cards(session, settings, scopes):
    rows = (await session.execute(catalog_query(settings, scopes))).all()
    found: dict[str, dict[str, str]] = {}
    for code, data in rows:
        if code in found and found[code]["name"] != data["name"]:
            raise AppError(
                409,
                "card_conflict",
                "Há versões conflitantes deste cartão na base. Solicite revisão.",
            )
        found[code] = {"code": code, "name": data["name"], "uf": data["uf"]}
    return sorted(found.values(), key=lambda row: normalize(row["name"]))


async def validate_card(session, settings, scopes, code):
    row = next((row for row in await cards(session, settings, scopes) if row["code"] == code), None)
    if not row:
        raise AppError(422, "invalid_card", "Selecione um cartão disponível na lista.")
    return row


def is_transport(question, state, question_id=None):
    text = normalize(question)
    if question_id:
        return question_id == "vale_transporte.segunda_via"
    if re.search(
        r"folha|atestado|holerite|salario|ferias|instrutor|escola|curso|capacitacao|refeicao|alimentacao",
        text,
    ):
        return False
    if re.search(r"sptrans|sou diadema|guarupas|cartao top", text):
        return True
    if re.search(
        r"segunda via|2[ªa°º]?\s*via|outro bilhete|outro cartao|perdi|roubar|roubo|furt|extravi|bloque",
        text,
    ) and re.search(r"cartao|bilhete|transporte|\bvt\b|onibus", text):
        return True
    if state.get("vt_stage") in {"selection", "active"}:
        return bool(
            text.strip().isdigit()
            or re.search(
                r"^(e |meu cartao|uso |utilizo |o meu)|taxa|quanto|custa|custo|valor|preco|prazo|demora|dias|pront|tempo|saldo|transfer|pago|pagar|retir|documento|trocar|cartao|\btop\b",
                text,
            )
        )
    return False


def card_candidates(question, rows):
    text = normalize(question)
    hits = []
    for row in rows:
        name = normalize(row["name"])
        prefix = name.split(" - ")[0]
        aliases = [name, prefix]
        if row["code"] == "182":
            aliases.append("guarulhos")
        if row["code"] == "89":
            aliases.append("sptrans")
        if row["code"] == "9156":
            aliases.append("top")
        if (
            any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text) for alias in aliases)
            or text.strip() == row["code"]
            or re.search(r"codigo(?: do beneficio)?\s*" + re.escape(row["code"]) + r"(?!\d)", text)
        ):
            hits.append(row["code"])
    return hits


def identify_card(question, rows):
    hits = card_candidates(question, rows)
    return hits[0] if len(hits) == 1 else None


def linkify(text):
    text = re.sub(r"https?://[^\s)]+", lambda m: f"[{m[0]}]({m[0]})", text)
    return re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", lambda m: f"[{m[0]}](mailto:{m[0]})", text)


def format_answer(row, fields):
    labels = {
        "requester": "Quem solicita",
        "payer": "Quem paga",
        "fee": "Taxa documentada",
        "payment": "Forma de pagamento",
        "procedure": "Procedimento",
    }
    blocks = [
        f"**{row['name']}** · Código {row['code']} · {row['uf']} [fonte:F1]",
        "Conforme o documento fornecido; valores e procedimentos têm vigência não confirmada. [fonte:F1]",
    ]
    for key in ["requester", "payer", "fee", "payment", "procedure"]:
        if key in fields:
            blocks.append(f"**{labels[key]}:** {linkify(row[key])} [fonte:F1]")
    if row["requester"] == "Empresa":
        blocks.append(
            "A solicitação cabe à empresa; o jovem deve seguir apenas as etapas de retirada que constam no procedimento. [fonte:F1]"
        )
    if "fee" in fields and "tarifa" in row["fee"].lower():
        blocks.append(
            "A taxa está expressa em número de tarifas; não foi convertida em reais. [fonte:F1]"
        )
    if row.get("review"):
        blocks.append("**Ponto para revisão:** " + row["review"] + " [fonte:F1]")
    if "procedure" in fields:
        blocks.append(
            "Documentos, contatos e prazos: considere apenas os especificados no procedimento acima; a tabela não detalha os demais. [fonte:F1]"
        )
    return "\n\n".join(blocks)
