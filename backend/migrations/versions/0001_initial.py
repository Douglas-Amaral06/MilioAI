"""Initial schema with pgvector. Frozen schema belongs to this revision."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def dates():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("identity", sa.String(500), nullable=False, unique=True),
        sa.Column("scopes", pg.JSONB(), nullable=False),
        *dates(),
    )
    op.create_table(
        "conversations",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "user_id", pg.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(100), nullable=False),
        *dates(),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_table(
        "messages",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", pg.UUID(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("sources", pg.JSONB(), nullable=False),
        sa.Column("outcome", sa.String(50)),
        *dates(),
        sa.CheckConstraint("role IN ('user','assistant')"),
        sa.CheckConstraint("status IN ('processing','complete','failed','cancelled')"),
        sa.UniqueConstraint("conversation_id", "request_id", "role"),
    )
    op.create_index("ix_message_history", "messages", ["conversation_id", "created_at", "id"])
    op.create_index(
        "ix_one_processing",
        "messages",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_table(
        "documents",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("origin", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(100), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        *dates(),
        sa.UniqueConstraint("sha256", "version", "scope", "embedding_model"),
    )
    op.create_index("ix_documents_domain", "documents", ["domain"])
    op.create_index("ix_documents_scope", "documents", ["scope"])
    op.create_table(
        "document_chunks",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "document_id",
            pg.UUID(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("embedding", Vector(), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_table(
        "attachments",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column(
            "conversation_id",
            pg.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", pg.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("message_id", pg.UUID(), sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_attachments_conversation_id", "attachments", ["conversation_id"])
    op.create_index("ix_attachments_user_id", "attachments", ["user_id"])


def downgrade():
    for table in [
        "attachments",
        "document_chunks",
        "documents",
        "messages",
        "conversations",
        "users",
    ]:
        op.drop_table(table)
