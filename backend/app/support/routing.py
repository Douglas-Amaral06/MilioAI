"""Procedure-first routing; no contacts or documentary contents in this module."""

import re

from app.agents.policies import owner
from app.agents.rh_frequency import normalize


def topic_for(question):
    text = normalize(question)
    if re.search(
        r"folha|ponto|frequencia|registr\w*.*curso|curso.*registr\w*|desconto duplicado", text
    ):
        return "folha_ponto"
    if re.search(
        r"vale.?transporte|\bvt\b|sptrans|bilhete|cartao.*transporte|segunda via.*cartao", text
    ):
        return "vale_transporte"
    if re.search(r"refeicao|alimentacao", text):
        return "vale_refeicao_alimentacao"
    if re.search(r"convenio|odontolog|academia|beneficio|plano de saude", text):
        return "beneficios"
    if re.search(r"salario|holerite|contracheque", text):
        return "salario"
    if re.search(r"ferias|rescisao", text):
        return "outros"
    if re.search(r"curso|aula|capacitacao|instrutor|professor|educacional|escolar", text):
        return "falta_curso"
    if re.search(r"trabalho|empresa", text) and re.search(
        r"atestad|falt|ausen|obito|comparecimento|comprovante|horas|gravidez|afastamento", text
    ):
        return "falta_trabalho"
    return None


def clarification(question, history=()):
    text = normalize(question)
    if topic_for(question):
        return None
    if re.search(r"atestad|comprovante de horas|certidao de obito", text):
        # Only explicit references can inherit a context; a new generic request cannot.
        if (
            re.search(r"esse|essa|isso|mesmo", text)
            and history
            and owner(history[-1].get("topic_id"))
        ):
            return None
        return "O documento se refere a uma ausência no curso ou no trabalho?"
    if re.search(r"descont", text):
        return "O desconto é por falta no curso, Vale-Transporte ou outro benefício?"
    return None


def split_requests(question):
    text = normalize(question)
    # Two procedures sharing the same course absence retain their own scenario.
    if (
        re.search(r"curso|capacitacao", text)
        and re.search(r"justific", text)
        and re.search(r"folha|ponto", text)
        and re.search(r"preench|registr", text)
    ):
        return [
            ("falta_curso", "Como justificar minha ausência no curso?"),
            ("folha_ponto", "Faltei no curso. Como registro isso na Folha Ponto?"),
        ]
    pieces = re.split(
        r"(?<=[?;])\s*|\s+e\s+(?=(?:como|qual|onde|quando|preciso|quero)\b)", question, flags=re.I
    )
    result = []
    for piece in pieces:
        if not piece.strip():
            continue
        topic = topic_for(piece)
        if result and (topic is None or topic == result[-1][0]):
            result[-1] = (result[-1][0], result[-1][1] + " " + piece)
        else:
            result.append((topic, piece.strip()))
    return result
