import re

from app.agents.rh_frequency import normalize
from app.support.catalog import get_topic


def explicit_topic(question):
    text = normalize(question)
    if re.search(r"\b(ferias|rescisao|decimo terceiro)\b", text):
        return "outros"
    if re.search(r"vale.?transporte|\bvt\b", text):
        return "vale_transporte"
    if re.search(r"vale.?refeicao|alimentacao|cartao de refeicao", text):
        return "vale_refeicao_alimentacao"
    if re.search(r"salario|salario|contracheque|holerite", text) and not re.search(
        r"folha|frequencia", text
    ):
        return "salario"
    if re.search(r"atestado", text):
        return "atestados"
    if re.search(r"(falta|ausencia|falto).*(curso|capacitacao)", text):
        return "falta_curso"
    if re.search(r"(falta|ausencia|falto).*(trabalho|empresa)", text):
        return "falta_trabalho"
    if re.search(r"\b(falta|faltas|ausencia|ausencias)\b", text):
        return "falta_trabalho"
    if re.search(r"\b(folha|ponto|frequencia|britanico|batida|jornada|horario|horarios)\b", text):
        return "folha_ponto"
    return None


def resolve_context(question, selected_topic, question_id, history, scopes):
    if selected_topic:
        get_topic(selected_topic, scopes)
    if question_id:
        chosen = selected_topic
    else:
        explicit = explicit_topic(question)
        if explicit:
            chosen = explicit
        elif selected_topic and selected_topic != "outros":
            chosen = (
                selected_topic
                if re.search(
                    r"\b(e |isso|essa|esse|qual|como|onde|prazo|atras|assin|documento|horario)",
                    normalize(question),
                )
                else "outros"
            )
        else:
            previous = next((m for m in reversed(history) if m["role"] == "user"), None)
            chosen = "outros"
            if previous and re.search(
                r"^(e |e se |isso|esse|essa)|\b(prazo|atrasar|assinar)\b", normalize(question)
            ):
                chosen = previous.get("topic_id") or explicit_topic(previous["content"]) or "outros"
    topic = get_topic(chosen or "outros", scopes)
    meaningful = (
        len(re.findall(r"[a-zA-ZÀ-ÿ]{2,}", question)) >= 2 or explicit_topic(question) is not None
    )
    return {
        "topic_id": topic.topic_id,
        "domain": topic.domain,
        "agent": topic.agent_id or "unavailable",
        "comprehensible": meaningful,
    }
