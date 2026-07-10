"""Add topic taxonomy: topics, item_topics, topic_proposals

Revision ID: 010
Revises: 009
Create Date: 2026-07-08

The cross-corpus navigation taxonomy (see docs/TOPICS_AND_TAGS_PLAN.md). Topics
are first-class rows because a closed, curated, filterable, reviewable set needs
identity — not a substring in a JSON blob. Tags stay as KnowledgeItem.tags.

Hand-written per the repo convention. `ux_item_topics_primary` is a PARTIAL
unique index (SQLite supports the WHERE clause) that enforces "at most one
primary topic per item" at the schema level — the ORM Boolean maps to 0/1, so
`WHERE is_primary` matches only the primary rows. No FTS involvement.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="user"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("slug", name="uq_topics_slug"),
    )
    op.create_index("ix_topics_status", "topics", ["status"])

    op.create_table(
        "item_topics",
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "topic_id",
            sa.String(36),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("assigned_by", sa.String(20), nullable=False, server_default="llm"),
        sa.Column("confidence", sa.Float),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_item_topics_topic", "item_topics", ["topic_id"])
    # At most one primary per item — partial unique index (hand-written SQL so
    # the WHERE clause survives; Alembic's create_index sqlite_where also works
    # but raw SQL is unambiguous and matches the repo's convention).
    op.execute(
        "CREATE UNIQUE INDEX ux_item_topics_primary "
        "ON item_topics(knowledge_item_id) WHERE is_primary"
    )

    op.create_table(
        "topic_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposed_label", sa.String(120), nullable=False),
        sa.Column("item_ids", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("batch_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime),
    )
    op.create_index("ix_topic_proposals_status", "topic_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_topic_proposals_status", table_name="topic_proposals")
    op.drop_table("topic_proposals")
    op.execute("DROP INDEX IF EXISTS ux_item_topics_primary")
    op.drop_index("ix_item_topics_topic", table_name="item_topics")
    op.drop_table("item_topics")
    op.drop_index("ix_topics_status", table_name="topics")
    op.drop_table("topics")
