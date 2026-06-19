"""Add description to youtube_metadata

Revision ID: 004
Revises: 003
Create Date: 2026-06-18

Stores the YouTube video description so summaries (and per-item chat) can be
grounded by it. Existing rows get NULL and self-heal on their next re-summarise
(the redo path fetches the description when it's missing).

Hand-written (autogenerate is unreliable for this repo). Not added to FTS — the
description is noisy and search stays scoped to title/summary/transcript/tags.
Plain nullable ADD COLUMN works in SQLite without a batch rebuild.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("youtube_metadata", sa.Column("description", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("youtube_metadata", "description")
