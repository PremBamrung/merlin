"""Rename knowledge_items.topics -> sections

Revision ID: 009
Revises: 008
Create Date: 2026-07-08

Frees the word "topics" for the new cross-corpus taxonomy (topics/item_topics
tables, added in migration 010). The old `topics` column was a misnomer: it
holds a per-video {"section heading": "12:34"} map scraped from the summary,
used to jump *within* one summary — that's now `sections`.

Plain `RENAME COLUMN` (SQLite >= 3.25). The `knowledge_fts` triggers index only
title/summary/raw_content/tags — NOT this column — so no FTS/trigger surgery is
needed and a native rename (no table rebuild) leaves them intact.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE knowledge_items RENAME COLUMN topics TO sections")


def downgrade() -> None:
    op.execute("ALTER TABLE knowledge_items RENAME COLUMN sections TO topics")
