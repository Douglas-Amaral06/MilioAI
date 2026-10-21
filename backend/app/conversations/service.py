import uuid

from sqlalchemy import select

from app.core.errors import AppError
from app.db.models import Conversation


async def owned(session, conversation_id: uuid.UUID, user_id: uuid.UUID, *, lock=False):
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    )
    if lock:
        query = query.with_for_update()
    conversation = await session.scalar(query)
    if conversation is None:
        raise AppError(404, "conversation_not_found", "Conversa não encontrada.")
    return conversation
