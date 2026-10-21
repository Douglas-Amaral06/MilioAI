import logging
import re
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agents.rh_frequency import (
    NO_EVIDENCE,
    OUT_OF_SCOPE,
    normalize,
    prompt,
    validate_references,
)
from app.api.schemas import SendInput
from app.core.errors import AppError
from app.rag.retrieval import retrieve
from app.rag.transport_extract import DOMAIN as TRANSPORT_DOMAIN
from app.rag.transport_ingest import transport_settings
from app.support.catalog import get_topic, resolve_question
from app.support.context import resolve_context
from app.support.operational import (
    CONFIG,
    CONTACT_SCOPE,
    SERVICES,
    authorize,
    available,
    confirmation,
    contact_text,
    detect,
    education_text,
    transition,
)
from app.support.transport import card_candidates, cards, format_answer, identify_card, is_transport

log = logging.getLogger("milioai")
CLARIFY = "Não consegui entender sua dúvida. Pode reformular a pergunta?"
AGENTS: dict[str, dict[str, Any]] = {"rh_frequency": {"domain": "rh_frequency", "prompt": prompt}}


class AgentState(TypedDict, total=False):
    conversation_id: str
    question: str
    question_id: str | None
    topic_id: str | None
    history: list[dict]
    scopes: tuple[str, ...]
    domain: str
    agent: str
    comprehensible: bool
    chunks: list[dict]
    answer: str
    sources: list[dict]
    outcome: str
    coverage: str
    support_state: dict
    action: dict | None
    detected_intent: str
    vt_route: bool
    retrieval_question: str


def build_graph(sessions, ollama, settings):
    async def transport_gate(state):
        action = state.get("action") or {}
        flow = state.get("support_state", {})
        routed = action.get("kind", "").startswith("card_") or is_transport(
            state["question"], flow, state.get("question_id")
        )
        if (
            not routed
            and flow.get("vt_stage") in {"selection", "active"}
            and not state.get("question_id")
            and not re.search(
                r"folha|atestado|holerite|salario|ferias|instrutor|curso|escola|refeicao|alimentacao",
                normalize(state["question"]),
            )
        ):
            async with sessions() as session:
                directory = await cards(session, settings, state["scopes"])
            routed = bool(card_candidates(state["question"], directory))
        return {"vt_route": routed}

    async def transport_response(state):
        writer = get_stream_writer()
        flow = dict(state.get("support_state", {}), stage="idle")
        action = state.get("action") or {}
        async with sessions() as session:
            directory = await cards(session, settings, state["scopes"])
        if not directory:
            text = "Não há cartões disponíveis na documentação autorizada para o seu acesso."
            writer({"event": "delta", "text": text})
            return {
                "answer": text,
                "sources": [],
                "outcome": "no_evidence",
                "support_state": dict(flow, vt_stage="idle"),
            }
        explicit = identify_card(state["question"], directory)
        chosen = action.get("benefit_code") or explicit
        declaration = re.search(
            r"meu cartao e|uso |utilizo |trocar|mudar|outro cartao", normalize(state["question"])
        )
        if (
            not chosen
            and flow.get("vt_stage") == "active"
            and not declaration
            and len(card_candidates(state["question"], directory)) < 2
        ):
            chosen = flow.get("selected_card_code")
        if action.get("kind") == "card_change":
            chosen = None
        if not chosen:
            text = "Claro! Qual cartão de transporte você utiliza?"
            flow["vt_stage"] = "selection"
            writer({"event": "delta", "text": text})
            return {
                "answer": text,
                "sources": [],
                "outcome": "card_selection",
                "support_state": flow,
            }
        if chosen not in {card["code"] for card in directory}:
            raise AppError(422, "invalid_card", "O cartão não está disponível na base autorizada.")
        card = next(card for card in directory if card["code"] == chosen)
        full = bool(
            action.get("kind") == "card_select" or explicit or flow.get("vt_stage") != "active"
        )
        question = (
            "Como solicitar a segunda via? Informe o procedimento completo, responsável, taxa e pagamento."
            if full
            else state["question"]
        )
        async with sessions() as session:
            chunks = await retrieve(
                session,
                ollama,
                transport_settings(settings),
                f"Segunda via. {card['name']}. {question}",
                state["scopes"],
                TRANSPORT_DOMAIN,
                benefit_code=chosen,
            )
        if len(chunks) != 1 or chunks[0]["benefit_code"] != chosen:
            raise AppError(
                409,
                "card_source_conflict",
                "Não foi possível confirmar um único registro para este cartão. Solicite revisão da base.",
            )
        fields = await ollama.transport_fields(question, chunks[0]["excerpt"])
        if full:
            fields = ["requester", "payer", "fee", "payment", "procedure"]
        answer = format_answer(chunks[0]["attributes"], fields)
        sources = validate_references(answer, chunks)
        flow.update(vt_stage="active", selected_card_code=chosen)
        writer({"event": "delta", "text": answer})
        writer({"event": "sources", "sources": sources})
        return {"answer": answer, "sources": sources, "outcome": "answered", "support_state": flow}

    async def operational_router(state):
        flow = dict(state.get("support_state", {}), vt_stage="idle")
        if not available(settings):
            return {"detected_intent": "documental", "support_state": dict(flow, stage="idle")}
        if state.get("action"):
            authorize(state["scopes"])
            return {"detected_intent": "action"}
        intent = await detect(
            ollama,
            state["question"],
            state.get("question_id"),
            state.get("topic_id"),
            state["history"],
            flow,
        )
        if intent not in {
            "course_contact",
            "course_certificate",
            "course_document",
            "instructor_known",
            "instructor_unknown",
        }:
            flow["stage"] = "idle"
        return {"detected_intent": intent, "support_state": flow}

    async def operational_response(state):
        intent = state["detected_intent"]
        flow = dict(state.get("support_state", {}))
        flow["detected_intent"] = intent
        if intent in SERVICES:
            flow["selected_service"] = intent
        if intent == "action" or intent in {"instructor_known", "instructor_unknown"}:
            authorize(state["scopes"])
            text, flow = transition(state.get("action") or {"kind": intent}, flow)
        elif intent == "ambiguous_document":
            text = "Qual documento você precisa entregar? É uma folha ponto, documento escolar ou atestado referente ao curso ou ao trabalho?"
        elif intent == "education_contact":
            authorize(state["scopes"])
            text = education_text()
            flow.update(asked=True, stage="contact")
        elif intent == "course_contact":
            if CONTACT_SCOPE not in state["scopes"]:
                text = "Seu acesso não permite consultar os contatos educacionais. Solicite autorização para este atendimento."
            elif flow.get("selected_instructor_id"):
                text = contact_text(flow["selected_instructor_id"])
                flow["stage"] = "contact"
            elif flow.get("asked"):
                text = "Você pode retomar a lista de instrutores abaixo ou continuar a conversa."
                flow["stage"] = "contact"
            else:
                text, flow = confirmation(flow, state["scopes"])
                text = text.strip()
        else:
            service = SERVICES[intent]
            if not service["enabled"]:
                text = "Esta orientação está indisponível no momento."
            else:
                text = f"Você pode acessar o [{CONFIG['link_label']}]({CONFIG['portal_url']}) para {service['guidance']}."
                if intent in {"send_timesheet", "course_certificate"}:
                    text += "\n\nConfirme com a área responsável o procedimento vigente; esta orientação não substitui outros canais informados."
                if intent == "course_certificate":
                    if flow.get("selected_instructor_id") and CONTACT_SCOPE in state["scopes"]:
                        text += "\n\n" + contact_text(flow["selected_instructor_id"])
                        flow["stage"] = "contact"
                    else:
                        extra, flow = confirmation(flow, state["scopes"])
                        text += extra
        get_stream_writer()({"event": "delta", "text": text})
        return {"answer": text, "sources": [], "outcome": "operational", "support_state": flow}

    async def finish_document(state):
        if state.get("detected_intent") != "course_document":
            return {}
        extra, flow = confirmation(state.get("support_state", {}), state["scopes"])
        if extra:
            get_stream_writer()({"event": "delta", "text": extra})
        return {"answer": state["answer"] + extra, "support_state": flow}

    async def validate_context(state):
        # Validate guided identifiers again at the orchestration boundary; ACL never comes from a topic.
        if state.get("question_id"):
            import uuid

            resolve_question(
                SendInput(
                    request_id=uuid.uuid4(),
                    topic_id=state.get("topic_id"),
                    question_id=state["question_id"],
                    content=state["question"],
                ),
                state["scopes"],
            )
        return resolve_context(
            state["question"],
            state.get("topic_id"),
            state.get("question_id"),
            state["history"],
            state["scopes"],
        )

    async def unavailable(state):
        text = OUT_OF_SCOPE if state["comprehensible"] else CLARIFY
        get_stream_writer()({"event": "delta", "text": text})
        return {
            "answer": text,
            "sources": [],
            "outcome": "out_of_scope" if state["comprehensible"] else "clarify",
        }

    async def retrieval(state):
        topic = get_topic(state["topic_id"], state["scopes"])
        previous = [
            m["content"]
            for m in state["history"]
            if m["role"] == "user"
            and (m.get("topic_id") == state["topic_id"] or not m.get("topic_id"))
        ][-1:]
        query = f"{topic.title}: {state['question']}"
        if not state.get("question_id") and previous and len(state["question"]) < 180:
            query += " Contexto: " + previous[-1]
        async with sessions() as session:
            chunks = await retrieve(
                session, ollama, settings, query[-2000:], state["scopes"], state["domain"]
            )
        log.info("retrieval_complete", extra={"agent": state["agent"], "chunk_count": len(chunks)})
        return {"chunks": chunks, "retrieval_question": query}

    async def assess(state):
        if not state["chunks"]:
            return {"coverage": "none"}
        result = await ollama.assess(
            state["retrieval_question"],
            state["chunks"],
            get_topic(state["topic_id"], state["scopes"]).title,
        )
        log.info(
            "evidence_assessed",
            extra={
                "agent": state["agent"],
                "coverage": result["coverage"],
                "chunk_count": len(result["chunks"]),
            },
        )
        return result

    async def generate(state):
        writer = get_stream_writer()
        if not state["chunks"]:
            writer({"event": "delta", "text": NO_EVIDENCE})
            return {"answer": NO_EVIDENCE, "outcome": "no_evidence"}
        # Evaluate sufficiency from source content; a retrieved result or catalog entry is not evidence by itself.
        # This instruction is part of the agent prompt, not a list of canned institutional answers.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in state["history"]
            if (not m.get("topic_id") or m.get("topic_id") == state["topic_id"])
        ]
        messages = AGENTS[state["agent"]]["prompt"](
            state["question"],
            history,
            state["chunks"],
            topic=get_topic(state["topic_id"], state["scopes"]).title,
        )
        answer = (
            "Material fictício de teste, sem validade institucional. "
            if any(c["is_test"] for c in state["chunks"])
            else ""
        )
        if answer:
            writer({"event": "delta", "text": answer})
        async for text in ollama.chat(messages):
            answer += text
            writer({"event": "delta", "text": text})
        return {
            "answer": answer,
            "outcome": "no_evidence"
            if answer.strip() == NO_EVIDENCE
            else "partial"
            if state.get("coverage") == "partial"
            else "answered",
        }

    async def validate(state):
        try:
            sources = validate_references(state["answer"], state["chunks"])
        except ValueError as error:
            log.warning("grounding_failed", extra={"error_type": str(error)})
            raise AppError(
                422,
                "grounding_failed",
                "Não foi possível confirmar as fontes da resposta. Tente reformular a pergunta.",
            ) from None
        get_stream_writer()({"event": "sources", "sources": sources})
        return {"sources": sources}

    graph = StateGraph(AgentState)
    graph.add_node("transport_gate", transport_gate)
    graph.add_node("transport", transport_response)
    graph.add_node("operational_router", operational_router)
    graph.add_node("operational", operational_response)
    graph.add_node("finish_document", finish_document)
    graph.add_node("validate_context", validate_context)
    graph.add_node("unavailable", unavailable)
    graph.add_node("retrieve", retrieval)
    graph.add_node("assess", assess)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_edge(START, "transport_gate")
    graph.add_conditional_edges(
        "transport_gate", lambda s: "transport" if s["vt_route"] else "operational_router"
    )
    graph.add_edge("transport", END)
    graph.add_conditional_edges(
        "operational_router",
        lambda s: (
            "transport"
            if s["detected_intent"] == "transport_replacement"
            else "validate_context"
            if s["detected_intent"] in {"documental", "course_document"}
            else "operational"
        ),
    )
    graph.add_edge("operational", END)
    graph.add_conditional_edges(
        "validate_context",
        lambda s: "retrieve" if s["agent"] in AGENTS and s["comprehensible"] else "unavailable",
    )
    graph.add_edge("unavailable", "finish_document")
    graph.add_edge("retrieve", "assess")
    graph.add_edge("assess", "generate")
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", "finish_document")
    graph.add_edge("finish_document", END)
    return graph.compile()
