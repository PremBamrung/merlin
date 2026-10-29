"""Add knowledge_items.surfaced_at — freshness, split from the ingest date

Revision ID: 016
Revises: 015
Create Date: 2026-10-29

`ingested_at` used to do two jobs: "when was this added" and "sort it to the
top". Redo-summary and refetch bumped it, which wrote over the real ingest
date. `surfaced_at` takes the second job — the Library's "Newest", the home
"New since" strip and topic recency sort on it — and is bumped by a redo, a
refetch, or "Bring to top" on a duplicate ingest. `ingested_at` is now set
once and never moved.

- Backfilled from `ingested_at`, so the current order is unchanged.
- Repair: items whose `ingested_at` had already been bumped (their first
  `ingest_*` task is more than an hour older) get the real date back from that
  task. `surfaced_at` keeps the bumped value, so they don't move in "Newest".
  The downgrade can't un-repair that, and doesn't need to.

Hand-written (autogenerate is unreliable for this repo). Plain ADD COLUMN, no
FTS/trigger changes.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_items", sa.Column("surfaced_at", sa.DateTime, nullable=True)
    )
    op.execute("UPDATE knowledge_items SET surfaced_at = ingested_at")
    op.create_index("ix_knowledge_surfaced", "knowledge_items", ["surfaced_at"])
    op.execute(
        """
        UPDATE knowledge_items
        SET ingested_at = (
            SELECT MIN(t.created_at) FROM background_tasks t
            WHERE t.knowledge_item_id = knowledge_items.id
              AND t.task_type LIKE 'ingest_%'
        )
        WHERE (
            SELECT MIN(t.created_at) FROM background_tasks t
            WHERE t.knowledge_item_id = knowledge_items.id
              AND t.task_type LIKE 'ingest_%'
        ) < datetime(ingested_at, '-1 hour')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_surfaced", table_name="knowledge_items")
    op.drop_column("knowledge_items", "surfaced_at")
