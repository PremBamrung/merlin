"""Add app_state (runtime key-value state that survives restarts)

Revision ID: 013
Revises: 012
Create Date: 2026-10-15

A tiny key → JSON table for process state that must outlive a container
rebuild. First user: the YouTube subtitle IP-block cooldown (until / current
escalation / tripped), which used to live only in memory, so every restart
forgot an active ban and re-probed the blocked transcript endpoint.

Plain `create_table`, hand-written for consistency with the other migrations.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),  # JSON
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_state")
