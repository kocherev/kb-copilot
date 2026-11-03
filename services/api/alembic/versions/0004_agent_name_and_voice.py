"""Add the agent name and voice to products

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("agent_name", sa.Text(), nullable=False, server_default="Shawn"),
    )
    op.add_column(
        "products",
        sa.Column("voice", sa.Text(), nullable=False, server_default="Sulafat"),
    )


def downgrade() -> None:
    op.drop_column("products", "voice")
    op.drop_column("products", "agent_name")
