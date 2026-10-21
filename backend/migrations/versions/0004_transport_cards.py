"""Exact benefit identity and structured source fields, additive to existing RAG."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_chunks", sa.Column("benefit_code", sa.String(32), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column(
            "attributes", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.create_index("ix_document_chunks_benefit_code", "document_chunks", ["benefit_code"])
    op.create_unique_constraint(
        "uq_chunk_benefit", "document_chunks", ["document_id", "benefit_code"]
    )


def downgrade():
    op.drop_constraint("uq_chunk_benefit", "document_chunks", type_="unique")
    op.drop_index("ix_document_chunks_benefit_code", table_name="document_chunks")
    op.drop_column("document_chunks", "attributes")
    op.drop_column("document_chunks", "benefit_code")
