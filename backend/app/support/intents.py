"""Conservative deterministic planning; guided actions keep their existing contract."""

import re

from app.agents.rh_frequency import normalize
from app.support.context import explicit_topic

SOCIAL = "Olá! Como posso ajudar? Posso orientar sobre Folha Ponto, Vale-Transporte, atestados e outros assuntos disponíveis."


def social_response(question):
    text = normalize(question).strip(" .!?,;:")
    if re.fullmatch(
        r"(?:(?:oi|ola|bom dia|boa tarde|boa noite|tudo bem|obrigad[oa]|valeu|ate mais)[ .!?,;:]*)+",
        text,
    ):
        if re.search(r"obrigad|valeu", text):
            return "Por nada! Estou à disposição."
        if "ate mais" in text:
            return "Até mais! Estou à disposição quando precisar."
        return SOCIAL
    return None


def intent_topic(question):
    if re.search(r"sptrans|bilhete|cartao|vale.?transporte|\bvt\b|onibus", normalize(question)):
        return "vale_transporte"
    return explicit_topic(question)


def plan(question):
    # Split only when a new explicit subject is present. Same-card cost follow-ups stay together.
    pieces = re.split(
        r"(?<=[?;])\s*|\s+e\s+(?=(?:como|qual|onde|quando|preciso|quero)\b)", question, flags=re.I
    )
    result = []
    for piece in pieces:
        if not piece.strip() or social_response(piece):
            continue
        topic = intent_topic(piece)
        if result and (topic is None or topic == result[-1][0]):
            result[-1] = (result[-1][0], result[-1][1] + " " + piece)
        else:
            result.append((topic, piece.strip()))
    # A compound subject without clear request boundaries needs clarification, never silent loss.
    for _, piece in result:
        text = normalize(piece)
        if re.search(r"folha|ponto|frequencia", text) and re.search(
            r"sptrans|bilhete|vale.?transporte", text
        ):
            return None
    return result if len(result) <= 3 else None
