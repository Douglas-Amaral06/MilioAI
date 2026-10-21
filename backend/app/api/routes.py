import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select, text, update

from app.api.schemas import (
    AttachmentOut,
    ConversationOut,
    MessageOut,
    SendInput,
    TitleInput,
    TopicInput,
)
from app.auth.dependencies import Principal, current_user
from app.conversations.service import owned
from app.core.errors import AppError
from app.db.models import Attachment, Conversation, Message
from app.messages.service import execute, prepare, sse
from app.storage.files import extract, validate_file
from app.support.catalog import TOPICS, Topic, get_topic
from app.support.operational import authorize, available, instructors
from app.support.transport import cards

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request, user: Principal = Depends(current_user)):
    async with request.app.state.sessions() as session:
        await session.execute(text("SELECT 1"))
    try:
        response = await request.app.state.ollama.client.get("/api/tags")
        response.raise_for_status()
        names = {m["name"] for m in response.json()["models"]}
        required = {
            request.app.state.settings.ollama_model,
            request.app.state.settings.embedding_model,
        }
        if not required.issubset(names):
            raise ValueError()
    except Exception:
        raise AppError(
            503, "model_unavailable", "Os modelos de IA não estão disponíveis."
        ) from None
    return {"status": "ready"}


@router.get("/me")
async def me(user: Principal = Depends(current_user)):
    return {"id": user.id}


@router.get("/conversations", response_model=list[ConversationOut])
async def conversations(
    request: Request,
    user: Principal = Depends(current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with request.app.state.sessions() as session:
        return (
            await session.scalars(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(Conversation.updated_at.desc(), Conversation.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()


@router.post("/conversations", status_code=201, response_model=ConversationOut)
async def create_conversation(
    payload: TitleInput, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        conversation = Conversation(user_id=user.id, title=payload.title)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation


@router.get("/conversations/{cid}", response_model=ConversationOut)
async def get_conversation(
    cid: uuid.UUID, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        return await owned(session, cid, user.id)


@router.patch("/conversations/{cid}", response_model=ConversationOut)
async def rename_conversation(
    cid: uuid.UUID, payload: TitleInput, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        conversation = await owned(session, cid, user.id, lock=True)
        if await session.scalar(
            select(Message.id).where(Message.conversation_id == cid, Message.status == "processing")
        ):
            raise AppError(409, "conversation_busy", "Aguarde a conclusão da resposta.")
        conversation.title = payload.title
        await session.commit()
        await session.refresh(conversation)
        return conversation


@router.delete("/conversations/{cid}", status_code=204)
async def delete_conversation(
    cid: uuid.UUID, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        conversation = await owned(session, cid, user.id, lock=True)
        if await session.scalar(
            select(Message.id).where(Message.conversation_id == cid, Message.status == "processing")
        ):
            raise AppError(409, "conversation_busy", "Aguarde a conclusão da resposta.")
        keys = (
            await session.scalars(
                select(Attachment.storage_key).where(Attachment.conversation_id == cid)
            )
        ).all()
        await session.delete(conversation)
        await session.commit()
    for key in keys:
        request.app.state.storage.remove(key)
    return Response(status_code=204)


@router.get("/conversations/{cid}/messages", response_model=list[MessageOut])
async def messages(
    cid: uuid.UUID,
    request: Request,
    user: Principal = Depends(current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with request.app.state.sessions() as session:
        await owned(session, cid, user.id, lock=True)
        await session.execute(
            update(Message)
            .where(
                Message.conversation_id == cid,
                Message.status == "processing",
                Message.updated_at
                < datetime.now(UTC)
                - timedelta(seconds=request.app.state.settings.ollama_timeout + 60),
            )
            .values(status="failed", content="", outcome="interrupted")
        )
        await session.commit()
        return (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == cid)
                .order_by(Message.created_at, Message.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()


@router.post("/conversations/{cid}/stream")
async def stream(
    cid: uuid.UUID, payload: SendInput, request: Request, user: Principal = Depends(current_user)
):
    prepared = await prepare(
        request.app.state.sessions, user, cid, payload, request.app.state.settings
    )

    async def events():
        iterator = execute(request.app, user, cid, payload, prepared)
        try:
            async for event in iterator:
                if await request.is_disconnected():
                    break
                yield sse(event)
        finally:
            await iterator.aclose()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{cid}/messages", response_model=MessageOut, status_code=201)
async def send(
    cid: uuid.UUID, payload: SendInput, request: Request, user: Principal = Depends(current_user)
):
    prepared = await prepare(
        request.app.state.sessions, user, cid, payload, request.app.state.settings
    )
    async for event in execute(request.app, user, cid, payload, prepared):
        if event["event"] == "error":
            raise AppError(event.get("status", 503), event["code"], event["message"])
        if event["event"] == "done":
            return event["message"]


@router.post("/conversations/{cid}/attachments", response_model=AttachmentOut, status_code=201)
async def upload(
    cid: uuid.UUID,
    request: Request,
    file: UploadFile = File(),
    user: Principal = Depends(current_user),
):
    settings = request.app.state.settings
    async with request.app.state.sessions() as session:
        await owned(session, cid, user.id)
    data = await file.read(settings.upload_max_bytes + 1)
    await file.close()
    name, media_type = validate_file(file.filename or "", data, settings.upload_max_bytes)
    key = await asyncio.to_thread(request.app.state.storage.put, data)
    try:
        if media_type == "application/pdf":
            await extract(request.app.state.storage.path(key), media_type)
        async with request.app.state.sessions() as session:
            await owned(session, cid, user.id, lock=True)
            attachment = Attachment(
                conversation_id=cid,
                user_id=user.id,
                name=name,
                media_type=media_type,
                storage_key=key,
                size=len(data),
            )
            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)
            return attachment
    except BaseException:
        request.app.state.storage.remove(key)
        raise


@router.get("/conversations/{cid}/attachments", response_model=list[AttachmentOut])
async def attachments(
    cid: uuid.UUID,
    request: Request,
    user: Principal = Depends(current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    async with request.app.state.sessions() as session:
        await owned(session, cid, user.id)
        return (
            await session.scalars(
                select(Attachment)
                .where(Attachment.conversation_id == cid, Attachment.user_id == user.id)
                .order_by(Attachment.created_at, Attachment.id)
                .offset(offset)
                .limit(limit)
            )
        ).all()


@router.get("/conversations/{cid}/attachments/{aid}")
async def download(
    cid: uuid.UUID, aid: uuid.UUID, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        await owned(session, cid, user.id)
        attachment = await session.scalar(
            select(Attachment).where(
                Attachment.id == aid,
                Attachment.conversation_id == cid,
                Attachment.user_id == user.id,
            )
        )
        if (
            attachment is None
            or not request.app.state.storage.path(attachment.storage_key).is_file()
        ):
            raise AppError(404, "attachment_not_found", "Anexo não encontrado.")
        return FileResponse(
            request.app.state.storage.path(attachment.storage_key),
            filename=attachment.name,
            media_type="application/octet-stream",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )


@router.delete("/conversations/{cid}/attachments/{aid}", status_code=204)
async def remove_attachment(
    cid: uuid.UUID, aid: uuid.UUID, request: Request, user: Principal = Depends(current_user)
):
    async with request.app.state.sessions() as session:
        await owned(session, cid, user.id, lock=True)
        attachment = await session.scalar(
            select(Attachment).where(
                Attachment.id == aid,
                Attachment.conversation_id == cid,
                Attachment.user_id == user.id,
                Attachment.message_id.is_(None),
            )
        )
        if attachment is None:
            raise AppError(404, "attachment_not_found", "Anexo não encontrado ou já enviado.")
        key = attachment.storage_key
        await session.delete(attachment)
        await session.commit()
    request.app.state.storage.remove(key)
    return Response(status_code=204)


@router.get("/support/topics", response_model=list[Topic])
async def support_topics(user: Principal = Depends(current_user)):
    return [t for t in TOPICS if t.enabled and set(t.required_scopes).issubset(user.scopes)]


@router.patch("/conversations/{cid}/topic", response_model=ConversationOut)
async def select_topic(
    cid: uuid.UUID, payload: TopicInput, request: Request, user: Principal = Depends(current_user)
):
    if payload.topic_id:
        get_topic(payload.topic_id, user.scopes)
    async with request.app.state.sessions() as session:
        conversation = await owned(session, cid, user.id, lock=True)
        if await session.scalar(
            select(Message.id).where(Message.conversation_id == cid, Message.status == "processing")
        ):
            raise AppError(409, "conversation_busy", "Aguarde a resposta atual desta conversa.")
        conversation.topic_id = payload.topic_id
        conversation.support_state = dict(
            conversation.support_state or {}, stage="idle", vt_stage="idle"
        )
        await session.commit()
        await session.refresh(conversation)
        return conversation


@router.get("/support/instructors")
async def instructor_directory(request: Request, user: Principal = Depends(current_user)):
    authorize(user.scopes)
    if not available(request.app.state.settings):
        raise AppError(403, "guidance_unavailable", "Orientação operacional indisponível.")
    return instructors()


@router.get("/support/transport-cards")
async def transport_card_directory(request: Request, user: Principal = Depends(current_user)):
    async with request.app.state.sessions() as session:
        return await cards(session, request.app.state.settings, user.scopes)
