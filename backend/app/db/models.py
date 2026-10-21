import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Dates:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Dates, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    identity: Mapped[str] = mapped_column(String(500), unique=True)
    scopes: Mapped[list] = mapped_column(JSONB, default=list)


class Conversation(Dates, Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100), default="Nova conversa")
    topic_id: Mapped[str | None] = mapped_column(String(80))
    support_state: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')"),
        CheckConstraint("status IN ('processing','complete','failed','cancelled')"),
        Index("ix_message_history", "conversation_id", "created_at", "id"),
        Index(
            "ix_one_processing",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
        UniqueConstraint("conversation_id", "request_id", "role"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    topic_id: Mapped[str | None] = mapped_column(String(80))
    question_id: Mapped[str | None] = mapped_column(String(120))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="complete")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    outcome: Mapped[str | None] = mapped_column(String(50))


class Document(Dates, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "sha256",
            "version",
            "scope",
            "embedding_model",
            "embedding_dimensions",
            "embedding_profile",
            name="uq_document_space",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    domain: Mapped[str] = mapped_column(String(50), index=True)
    approved: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="approved", server_default="approved")
    validation_only: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    embedding_profile: Mapped[str] = mapped_column(
        String(64), default="legacy", server_default="legacy"
    )
    version: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(100), index=True)
    origin: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(255))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    is_test: Mapped[bool] = mapped_column(default=False)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        UniqueConstraint("document_id", "benefit_code", name="uq_chunk_benefit"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    benefit_code: Mapped[str | None] = mapped_column(String(32), index=True)
    attributes: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    content: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(
        String(255), default="Documento", server_default="Documento"
    )
    sha256: Mapped[str] = mapped_column(String(64), default="", server_default="")
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    # Variable storage dimension; retrieval filters the exact model + dimension.
    # Exact cosine scan is intentional for the small initial corpus (no incompatible shared ANN index).
    embedding: Mapped[list[float]] = mapped_column(Vector())


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="stored")
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
