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
    from app.support.routing import split_requests
    pieces = split_requests(question)
    result = []
    for topic, piece in pieces:
        if social_response(piece):
            continue
        result.append((topic or intent_topic(piece), piece))
    # A compound subject without clear request boundaries needs clarification, never silent loss.
    for _, piece in result:
        text = normalize(piece)
        if re.search(r"folha|ponto|frequencia", text) and re.search(
            r"sptrans|bilhete|vale.?transporte", text
        ):
            return None
    return result if len(result) <= 3 else None
