import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.api.schemas import MessageOut
from app.conversations.service import owned
from app.core.errors import AppError
from app.db.models import Attachment, Message
from app.support.catalog import resolve_question
from app.support.context import resolve_context
from app.support.operational import available, confirmation_action, validate_action
from app.support.transport import validate_card

log = logging.getLogger("milioai")


def wire(message):
    return MessageOut.model_validate(message).model_dump(mode="json")


async def prepare(sessions, principal, cid, payload, settings):
    async with sessions() as session:
        conversation = await owned(session, cid, principal.id, lock=True)
        support_state = dict(conversation.support_state or {})
        if payload.action:
            if payload.content or payload.question_id or payload.attachment_ids:
                raise AppError(422, "invalid_action", "Envie a ação separadamente da mensagem.")
            if payload.action.kind.startswith("card_"):
                if payload.action.kind == "card_select":
                    if support_state.get("vt_stage") != "selection":
                        raise AppError(409, "invalid_flow", "Abra a seleção de cartões primeiro.")
                    card = await validate_card(
                        session, settings, principal.scopes, payload.action.benefit_code
                    )
                    text = "Cartão selecionado: " + card["name"]
                else:
                    text = "Trocar cartão de transporte."
            elif not available(settings):
                raise AppError(403, "guidance_unavailable", "Orientação operacional indisponível.")
            else:
                text = validate_action(payload.action, support_state, principal.scopes)
        else:
            text = resolve_question(payload, principal.scopes)
        # A process killed during generation cannot hold the conversation forever.
        # Lease exceeds the hard total request timeout; never reclaims an active request.
        await session.execute(
            update(Message)
            .where(
                Message.conversation_id == cid,
                Message.status == "processing",
                Message.updated_at
                < datetime.now(UTC) - timedelta(seconds=settings.ollama_timeout + 60),
            )
            .values(status="failed", content="", outcome="interrupted")
        )
        existing = (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == cid, Message.request_id == payload.request_id)
                .order_by(Message.created_at)
            )
        ).all()
        if existing:
            raise AppError(
                409,
                "duplicate_request",
                "Esta mensagem já foi recebida. Atualize a conversa antes de reenviar.",
            )
        processing = await session.scalar(
            select(Message.id).where(Message.conversation_id == cid, Message.status == "processing")
        )
        if processing:
            raise AppError(409, "conversation_busy", "Aguarde a resposta atual desta conversa.")
        attachments = []
        for aid in set(payload.attachment_ids):
            attachment = await session.scalar(
                select(Attachment).where(
                    Attachment.id == aid,
                    Attachment.conversation_id == cid,
                    Attachment.user_id == principal.id,
                    Attachment.message_id.is_(None),
                )
            )
            if attachment is None:
                raise AppError(404, "attachment_not_found", "Anexo não encontrado ou já utilizado.")
            attachments.append(attachment)
        history_rows = list(
            reversed(
                (
                    await session.scalars(
                        select(Message)
                        .where(Message.conversation_id == cid, Message.status == "complete")
                        .order_by(Message.created_at.desc(), Message.id.desc())
                        .limit(16)
                    )
                ).all()
            )
        )
        history: list[dict] = []
        budget = settings.history_chars
        for row in reversed(history_rows):
            if len(row.content) > budget:
                break
            history.insert(0, {"role": row.role, "content": row.content, "topic_id": row.topic_id})
            budget -= len(row.content)
        if payload.action or confirmation_action(text, support_state):
            context = {"topic_id": conversation.topic_id or "falta_curso"}
        else:
            context = resolve_context(
                text,
                payload.topic_id if payload.topic_id is not None else conversation.topic_id,
                payload.question_id,
                history,
                principal.scopes,
            )
        conversation.topic_id = context["topic_id"]
        created = datetime.now(UTC)
        user = Message(
            conversation_id=cid,
            request_id=payload.request_id,
            role="user",
            created_at=created,
            content=text,
            topic_id=context["topic_id"],
            question_id=payload.question_id,
            status="complete",
        )
        assistant = Message(
            conversation_id=cid,
            request_id=payload.request_id,
            role="assistant",
            created_at=created + timedelta(microseconds=1),
            content="",
            status="processing",
            topic_id=context["topic_id"],
            question_id=payload.question_id,
        )
        session.add_all([user, assistant])
        await session.flush()
        for attachment in attachments:
            attachment.message_id = user.id
        if conversation.title == "Nova conversa":
            conversation.title = text[:64]
        conversation.updated_at = datetime.now(UTC)
        await session.commit()
        return user, assistant, history, support_state


async def finalize(
    sessions, cid, principal, mid, *, content="", sources=None, status, outcome, support_state=None
):
    async with sessions() as session:
        conversation = await owned(session, cid, principal.id, lock=True)
        message = await session.get(Message, mid)
        if message and message.status == "processing":
            message.content, message.sources = content, sources or []
            message.status, message.outcome = status, outcome
            conversation.updated_at = datetime.now(UTC)
            if support_state is not None:
                conversation.support_state = support_state
            await session.commit()
        return message


def sse(event):
    return f"event: {event['event']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def execute(app, principal, cid, payload, prepared):
    user, assistant, history, support_state = prepared
    start = time.monotonic()
    settings = app.state.settings
    result = {}
    succeeded = False
    completed = False
    try:
        yield {"event": "start", "user": wire(user), "assistant": wire(assistant)}
        async with asyncio.timeout(settings.ollama_timeout):
            async for mode, value in app.state.graph.astream(
                {
                    "conversation_id": str(cid),
                    "question": user.content,
                    "topic_id": user.topic_id,
                    "question_id": user.question_id,
                    "history": history,
                    "scopes": principal.scopes,
                    "support_state": support_state,
                    "action": payload.action.model_dump() if payload.action else None,
                    "chunks": [],
                    "sources": [],
                },
                stream_mode=["custom", "updates"],
            ):
                if mode == "custom":
                    yield value
                else:
                    for node in value.values():
                        if node:
                            result.update(node)
        message = await finalize(
            app.state.sessions,
            cid,
            principal,
            assistant.id,
            content=result["answer"],
            sources=result.get("sources", []),
            status="complete",
            outcome=result.get("outcome", "answered"),
            support_state=result.get("support_state", support_state),
        )
        succeeded = True
        completed = True
        yield {"event": "done", "message": wire(message)}
    except (asyncio.CancelledError, GeneratorExit):
        raise
    except Exception as error:
        log.warning("response_failed", extra={"error_type": type(error).__name__})
        await finalize(
            app.state.sessions, cid, principal, assistant.id, status="failed", outcome="error"
        )
        succeeded = True
        if isinstance(error, AppError):
            yield {
                "event": "error",
                "code": error.code,
                "message": error.message,
                "status": error.status,
            }
        else:
            yield {
                "event": "error",
                "code": "processing_failed",
                "status": 504 if isinstance(error, TimeoutError) else 503,
                "message": "Não foi possível concluir a resposta. Tente novamente.",
            }
    finally:
        if not succeeded:
            # Shield cleanup against ASGI cancellation; stale lease is the fallback on hard process death.
            cleanup = asyncio.create_task(
                finalize(
                    app.state.sessions,
                    cid,
                    principal,
                    assistant.id,
                    status="cancelled",
                    outcome="interrupted",
                )
            )
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                pass
        log.info(
            "response_finished",
            extra={
                "agent": result.get("agent"),
                "duration_ms": round((time.monotonic() - start) * 1000),
                "success": completed,
            },
        )
