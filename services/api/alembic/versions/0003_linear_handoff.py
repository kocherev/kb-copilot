"""Add Linear connections and escalations

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "linear_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("access_token", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token", sa.LargeBinary(), nullable=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=True),
        sa.Column("workspace_name", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Text(), nullable=False),
        sa.Column("team_key", sa.Text(), nullable=False),
        sa.Column("team_name", sa.Text(), nullable=False),
        sa.Column("connected_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id"),
    )
    op.create_table(
        "linear_state_uses",
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_table(
        "escalations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("room", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("issue_identifier", sa.Text(), nullable=True),
        sa.Column("issue_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_escalations_org_id"), "escalations", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_escalations_org_id"), table_name="escalations")
    op.drop_table("escalations")
    op.drop_table("linear_state_uses")
    op.drop_table("linear_connections")
