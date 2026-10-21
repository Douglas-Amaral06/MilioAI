"""Guided support context and traceable semantic corpus, additive migration."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("topic_id", sa.String(80)))
    op.add_column("messages", sa.Column("topic_id", sa.String(80)))
    op.add_column("messages", sa.Column("question_id", sa.String(120)))
    op.add_column(
        "documents", sa.Column("status", sa.String(20), nullable=False, server_default="approved")
    )
    op.execute(
        "UPDATE documents SET status = CASE WHEN approved THEN 'approved' ELSE 'pending' END"
    )
    op.add_column(
        "documents",
        sa.Column("validation_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "documents",
        sa.Column("embedding_profile", sa.String(64), nullable=False, server_default="legacy"),
    )
    op.add_column(
        "document_chunks",
        sa.Column("section", sa.String(255), nullable=False, server_default="Documento"),
    )
    op.add_column(
        "document_chunks", sa.Column("sha256", sa.String(64), nullable=False, server_default="")
    )
    op.drop_constraint(
        "documents_sha256_version_scope_embedding_model_key", "documents", type_="unique"
    )
    op.create_unique_constraint(
        "uq_document_space",
        "documents",
        [
            "sha256",
            "version",
            "scope",
            "embedding_model",
            "embedding_dimensions",
            "embedding_profile",
        ],
    )


def downgrade():
    # Never collapse embedding spaces implicitly; downgrade requires reviewed data migration.
    raise RuntimeError(
        "Forward-only: preserve corpus and topic history; restore a reviewed backup if rollback is required"
    )
