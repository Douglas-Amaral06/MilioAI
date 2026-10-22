"""Backend capabilities. A topic, prompt or user text cannot grant a capability."""

import re
from dataclasses import dataclass

from app.agents.rh_frequency import prompt as base_prompt


@dataclass(frozen=True)
class Specialist:
    identifier: str
    domain: str
    topics: tuple[str, ...]
    tools: tuple[str, ...]
    tone: str


SPECIALISTS = {
    "educational_agent": Specialist(
        "educational_agent",
        "education",
        ("falta_curso", "educacional"),
        ("documents", "contacts", "instructors", "operational"),
        "Educacional: acolhedor, claro e orientativo. Curso, instrutores e justificativas do curso; nunca invente endereço, unidade ou instrutor.",
    ),
    "frequency_agent": Specialist(
        "frequency_agent",
        "rh_frequency",
        ("folha_ponto", "falta_trabalho", "atestados"),
        ("documents", "contacts", "operational"),
        "Frequência: claro, preciso e profissional. Folha Ponto e ausências no trabalho. Nunca aprove documentos ou direitos; preserve condições de registro e prazos.",
    ),
    "service_agent": Specialist(
        "service_agent",
        "benefits",
        ("vale_transporte", "vale_refeicao_alimentacao", "beneficios"),
        ("documents", "contacts", "transport"),
        "Atendimento: prestativo, organizado e objetivo. Benefícios e cartões; elegibilidade, taxas e procedimentos apenas quando documentados. Operadora não é contato departamental.",
    ),
}


def owner(topic):
    return next((key for key, policy in SPECIALISTS.items() if topic in policy.topics), None)


def authorize_tool(agent_id, tool, domain=None):
    policy = SPECIALISTS.get(agent_id)
    if not policy or tool not in policy.tools:
        raise ValueError("Unauthorized specialist capability")
    domains = {policy.domain}
    if agent_id == "service_agent" and tool in {"documents", "transport"}:
        domains.add("beneficios.vale_transporte.segunda_via")
    if domain is not None and domain not in domains:
        raise ValueError("Unauthorized specialist domain")
    return policy


def history_for(agent_id, history):
    from app.support.routing import split_requests

    # Untagged and composed turns cannot be attributed safely to one specialist.
    selected = []
    for message in history:
        if owner(message.get("topic_id")) != agent_id or message.get("role") not in {
            "user",
            "assistant",
        }:
            continue
        routing_text = re.sub(r"https?://[^\s)]+", "", message["content"])
        if len(split_requests(routing_text)) > 1 or "**Benefício" in message["content"]:
            continue
        selected.append(message)
    return selected


def specialist_prompt(agent_id, question, history, chunks, topic=None):
    policy = authorize_tool(agent_id, "documents")
    messages = base_prompt(question, history_for(agent_id, history), chunks, topic)
    messages[0]["content"] = (
        messages[0]["content"].replace("agente de RH Frequência", "assistente institucional")
        + "\n"
        + policy.tone
        + " Responda diretamente, com linguagem natural, sem emojis. O histórico resolve referências e repetições, mas nunca fornece fatos."
    )
    return messages


def specialist_settings(settings, agent_id):
    policy = authorize_tool(agent_id, "documents")
    field = {"education": "education_kb_version", "benefits": "benefits_kb_version"}.get(
        policy.domain
    )
    version = getattr(settings, field, "") if field else ""
    return settings.model_copy(update={"active_kb_version": version}) if version else settings
