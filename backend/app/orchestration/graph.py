import asyncio
import logging
import re
import time
from typing import Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from app.agents.rh_frequency import (
    NO_EVIDENCE,
    OUT_OF_SCOPE,
    document_rules,
    normalize,
    prompt,
    render_document_rule,
    requires_document_rule,
    validate_references,
)
from app.api.schemas import SendInput
from app.core.errors import AppError
from app.rag.retrieval import retrieve
from app.rag.transport_extract import DOMAIN as TRANSPORT_DOMAIN
from app.rag.transport_ingest import transport_settings
from app.support.catalog import TOPICS, get_topic, resolve_question
from app.support.context import resolve_context
from app.support.intents import plan, social_response
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
    skip_plan: bool
    planned: list
    entry_route: str
    document_question: str
    generation_mode: str
    deadline: float
    retrieval_question: str


def build_graph(sessions, ollama, settings):
    async def entry(state):
        deadline = state.get("deadline", time.monotonic() + settings.ollama_timeout - 2)
        if state.get("skip_plan") or state.get("action") or state.get("question_id"):
            return {"entry_route": "transport_gate", "deadline": deadline}
        social = social_response(state["question"])
        if social:
            get_stream_writer()({"event": "delta", "text": social})
            return {
                "entry_route": "end",
                "answer": social,
                "sources": [],
                "outcome": "social",
                "deadline": deadline,
            }
        planned = plan(state["question"])
        log.info(
            "intents_identified",
            extra={
                "conversation_id": state.get("conversation_id"),
                "domains": [p[0] for p in planned] if planned else [],
                "intent_count": len(planned or []),
            },
        )
        if planned is None:
            text = "Pode separar as solicitações e indicar o assunto de cada uma? Atendo até três solicitações independentes por mensagem."
            get_stream_writer()({"event": "delta", "text": text})
            return {
                "entry_route": "end",
                "answer": text,
                "sources": [],
                "outcome": "clarify",
                "deadline": deadline,
            }
        return {
            "entry_route": "multiple" if len(planned) > 1 else "transport_gate",
            "planned": planned,
            "deadline": deadline,
        }

    async def multiple(state):
        sections, sources, outcomes = [], [], []
        flow = dict(state.get("support_state", {}))
        for index, (topic, question) in enumerate(state["planned"]):
            started = time.monotonic()
            child = dict(
                state,
                question=question,
                topic_id=topic,
                question_id=None,
                action=None,
                skip_plan=True,
                chunks=[],
                sources=[],
                answer="",
                history=[m for m in state["history"] if m.get("topic_id") == topic],
                support_state=flow,
            )
            result = {}
            try:
                if topic:
                    get_topic(topic, state["scopes"])
                remaining = state["deadline"] - time.monotonic()
                child["deadline"] = time.monotonic() + max(
                    0.01, remaining / (len(state["planned"]) - index)
                )
                async with asyncio.timeout(max(0.01, child["deadline"] - time.monotonic())):
                    # Consume child events privately; publish only the completed composition.
                    async for mode, value in compiled.astream(
                        child, stream_mode=["updates", "custom"]
                    ):
                        if mode == "updates":
                            for update in value.values():
                                if update:
                                    result.update(update)
                text = result["answer"]
                local = result.get("sources", [])
                chunks = result.get("chunks", [])
                # Replace all aliases with immutable chunk IDs to prevent F1 collisions.
                aliases = {f"F{i + 1}": c["id"] for i, c in enumerate(chunks)}
                text = re.sub(
                    r"\[fonte:([^]]+)\]",
                    lambda m, aliases=aliases: "[fonte:" + str(aliases.get(m[1], m[1])) + "]",
                    text,
                )
                sources.extend(local)
                outcomes.append(result.get("outcome", "error"))
                flow = result.get("support_state", flow)
            except Exception as error:
                log.warning(
                    "intent_failed",
                    extra={
                        "conversation_id": state.get("conversation_id"),
                        "domain": topic,
                        "error_type": type(error).__name__,
                    },
                )
                text = (
                    "Não foi possível concluir esta orientação. Tente novamente para este assunto."
                )
                outcomes.append("error")
            title = next((t.title for t in TOPICS if t.topic_id == topic), "Outra solicitação")
            sections.append(f"**{title}**\n\n{text}")
            log.info(
                "intent_finished",
                extra={
                    "conversation_id": state.get("conversation_id"),
                    "domain": topic,
                    "outcome": outcomes[-1],
                    "duration_ms": round((time.monotonic() - started) * 1000),
                },
            )
        answer = "\n\n".join(sections)
        outcome = (
            "answered"
            if all(o in {"answered", "operational"} for o in outcomes)
            else "partial"
            if any(o in {"answered", "operational", "partial"} for o in outcomes)
            else "no_evidence"
        )
        writer = get_stream_writer()
        writer({"event": "delta", "text": answer})
        writer({"event": "sources", "sources": sources})
        return {"answer": answer, "sources": sources, "outcome": outcome, "support_state": flow}

    async def transport_gate(state):
        action = state.get("action") or {}
        flow = state.get("support_state", {})
        routed = action.get("kind", "").startswith("card_") or is_transport(
            state["question"], flow, state.get("question_id")
        )
        if (
            not routed
            and (
                flow.get("vt_stage") in {"selection", "active"}
                or re.search(
                    r"via|taxa|tarifa|cartao|bilhete|solicit|retir|bloque|codigo|prazo|pronto|paga|custa|pede|levo|emite|dados|endereco",
                    normalize(state["question"]),
                )
            )
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
            r"meu cartao e|uso |utilizo |trocar|troquei|mudar|mudei|outro cartao|codigo|^\s*\d+\s*$",
            normalize(state["question"]),
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
        return {
            "answer": answer,
            "chunks": chunks,
            "sources": sources,
            "outcome": "answered",
            "support_state": flow,
        }

    async def operational_router(state):
        flow = dict(state.get("support_state", {}))
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
        if intent != "transport_replacement":
            flow["vt_stage"] = "idle"
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
        elif intent == "personal_unavailable":
            text = "Não tenho acesso ao seu saldo atual, salário líquido ou dados pessoais de pagamento. Consulte o canal responsável pelo seu benefício ou pagamento."
        elif intent == "education_validation":
            text = f"A configuração local dos contatos educacionais tem status {CONFIG['validation_status']}. Não há confirmação de validação institucional desses contatos."
        elif intent == "instructor_selection_required":
            authorize(state["scopes"])
            text = "Selecione o instrutor na lista abaixo para confirmar o contato. Informar um identificador na mensagem não confirma a seleção."
            flow.update(asked=True, stage="selection")
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
        from app.support.operational import provenance

        if intent != "personal_unavailable":
            flow["operational_provenance"] = provenance(intent)
        outcome = (
            "clarify"
            if intent in {"ambiguous_document", "instructor_selection_required"}
            else "no_evidence"
            if intent == "personal_unavailable"
            else "operational"
        )
        domain = "operational"
        if intent == "personal_unavailable":
            domain = (
                "vale_transporte"
                if re.search(r"cartao|bilhete|saldo", normalize(state["question"]))
                else "salario"
            )
        return {
            "answer": text,
            "sources": [],
            "outcome": outcome,
            "support_state": flow,
            "domain": domain,
        }

    async def finish_document(state):
        if (
            re.search(r"conecta", normalize(state["question"]))
            and re.search(r"pdf|canais", normalize(state["question"]))
            and state.get("sources")
        ):
            from app.support.operational import provenance

            flow = dict(state.get("support_state", {}))
            flow["operational_provenance"] = provenance("send_timesheet")
            extra = f"\n\n**Ponto para revisão:** A configuração operacional local indica o [{CONFIG['link_label']}]({CONFIG['portal_url']}) para {SERVICES['send_timesheet']['guidance']}; seu status de validação é {CONFIG['validation_status']}. Confirme com o RH Jovem o canal vigente. Não foi estabelecida precedência entre a orientação operacional e o documento."
            get_stream_writer()({"event": "delta", "text": extra})
            return {"answer": state["answer"] + extra, "support_state": flow}
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
        question = state["question"]
        # Retrieve/generate the documentary part of a mixed-provenance comparison.
        # Operational configuration is attached separately after document grounding.
        if re.search(r"conecta", normalize(question)) and re.search(
            r"pdf|canais", normalize(question)
        ):
            question = "Quais canais de envio da folha ponto constam na documentação?"
        query = f"{topic.title}: {question}"
        if not state.get("question_id") and previous and len(state["question"]) < 180:
            query += " Contexto: " + previous[-1]
        async with sessions() as session:
            chunks = await retrieve(
                session, ollama, settings, query[-2000:], state["scopes"], state["domain"]
            )
        log.info("retrieval_complete", extra={"agent": state["agent"], "chunk_count": len(chunks)})
        return {"chunks": chunks, "retrieval_question": query, "document_question": question}

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
        if requires_document_rule(state["question"]):
            rules = document_rules(state["chunks"])
            selected = await ollama.select_document_rule(state["retrieval_question"], rules)
            answer = render_document_rule(selected, rules)
            if answer != NO_EVIDENCE and any(c["is_test"] for c in state["chunks"]):
                answer = "Material fictício de teste, sem validade institucional. " + answer
            return {
                "answer": answer,
                "outcome": "no_evidence"
                if answer == NO_EVIDENCE
                else "partial"
                if state.get("coverage") == "partial"
                else "answered",
                "generation_mode": "source_rule",
            }
        # Evaluate sufficiency from source content; a retrieved result or catalog entry is not evidence by itself.
        # This instruction is part of the agent prompt, not a list of canned institutional answers.
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in state["history"]
            if (not m.get("topic_id") or m.get("topic_id") == state["topic_id"])
        ]
        messages = AGENTS[state["agent"]]["prompt"](
            state.get("document_question", state["question"]),
            history,
            state["chunks"],
            topic=get_topic(state["topic_id"], state["scopes"]).title,
        )
        answer = (
            "Material fictício de teste, sem validade institucional. "
            if any(c["is_test"] for c in state["chunks"])
            else ""
        )
        async for text in ollama.chat(messages):
            answer += text
        return {
            "answer": answer,
            "outcome": "no_evidence"
            if answer.strip() == NO_EVIDENCE
            else "partial"
            if state.get("coverage") == "partial"
            else "answered",
        }

    async def validate(state):
        answer = state["answer"]
        sources = []
        for attempt in range(2):
            try:
                sources = validate_references(answer, state["chunks"])
                if sources:
                    try:
                        async with asyncio.timeout(
                            max(0.1, (state["deadline"] - time.monotonic()) / 2)
                        ):
                            supported = await ollama.verify_grounding(answer, state["chunks"])
                    except (AppError, TimeoutError):
                        supported = False
                    if not supported:
                        raise ValueError("Unsupported claim")
                break
            except ValueError as error:
                log.warning(
                    "grounding_failed",
                    extra={
                        "conversation_id": state.get("conversation_id"),
                        "error_type": str(error),
                        "repair_attempt": attempt,
                    },
                )
                remaining = state.get("deadline", 0) - time.monotonic()
                if state.get("generation_mode") == "source_rule" or attempt or remaining < 5:
                    answer, sources = NO_EVIDENCE, []
                    break
                log.info(
                    "grounding_repair", extra={"conversation_id": state.get("conversation_id")}
                )
                messages = prompt(
                    state.get("document_question", state["question"]),
                    [],
                    state["chunks"],
                    topic=get_topic(state["topic_id"], state["scopes"]).title,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"A resposta anterior foi rejeitada: {error}. Refaça a resposta à PERGUNTA ATUAL usando somente afirmações sustentadas. Resolva primeiro a condição e a exceção aplicáveis na fonte. Entregue apenas a resposta final, em um parágrafo curto, citando cada afirmação; não inclua rascunhos ou alternativas contraditórias. Se não houver suporte use a resposta de informação insuficiente. /no_think",
                    }
                )
                try:
                    async with asyncio.timeout(max(0.1, remaining / 2)):
                        answer = "".join([text async for text in ollama.chat(messages)])
                except (AppError, TimeoutError):
                    answer, sources = NO_EVIDENCE, []
                    break
        writer = get_stream_writer()
        # Empty-evidence generation already emitted the trusted fallback.
        if state["chunks"]:
            writer({"event": "delta", "text": answer})
        writer({"event": "sources", "sources": sources})
        return {
            "answer": answer,
            "sources": sources,
            "outcome": "no_evidence" if answer == NO_EVIDENCE else state["outcome"],
        }

    def observed(name, function):
        async def run(state):
            started = time.monotonic()
            try:
                return await function(state)
            finally:
                log.info(
                    "stage_finished",
                    extra={
                        "conversation_id": state.get("conversation_id"),
                        "stage": name,
                        "domain": state.get("domain"),
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    },
                )

        return run

    graph = StateGraph(AgentState)
    graph.add_node("entry", observed("entry", entry))
    graph.add_node("multiple", observed("multiple", multiple))
    graph.add_node("transport_gate", observed("transport_gate", transport_gate))
    graph.add_node("transport", observed("transport", transport_response))
    graph.add_node("operational_router", observed("operational_router", operational_router))
    graph.add_node("operational", observed("operational", operational_response))
    graph.add_node("finish_document", observed("finish_document", finish_document))
    graph.add_node("validate_context", observed("validate_context", validate_context))
    graph.add_node("unavailable", observed("unavailable", unavailable))
    graph.add_node("retrieve", observed("retrieve", retrieval))
    graph.add_node("assess", observed("assess", assess))
    graph.add_node("generate", observed("generate", generate))
    graph.add_node("validate", observed("validate", validate))
    graph.add_edge(START, "entry")
    graph.add_conditional_edges(
        "entry", lambda s: END if s["entry_route"] == "end" else s["entry_route"]
    )
    graph.add_edge("multiple", END)
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
    compiled = graph.compile()
    return compiled
