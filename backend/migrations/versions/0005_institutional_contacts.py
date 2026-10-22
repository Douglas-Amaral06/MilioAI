"""Persist structured response entities without altering documents or approvals."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "messages",
        sa.Column(
            "contacts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )


def downgrade():
    op.drop_column("messages", "contacts")
