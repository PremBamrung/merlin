"""Add youtube_comments + youtube_metadata.comments_fetched_at

Revision ID: 015
Revises: 014
Create Date: 2026-10-16

A video's top-level comments (YouTube's "Top" order, re-sorted pinned-first
then by likes), fetched best-effort at ingest and on demand from the Reader.
They ground a "What Viewers Say" summary section and are readable in chat.

- `youtube_comments` — one row per comment; `rank` is the display order. The
  whole set is replaced on each fetch, so there's no per-comment upsert.
- `youtube_metadata.comments_fetched_at` — when the set was last fetched.
  NULL = never fetched (older items; the redo path self-heals them), which is
  how "no comments" is told apart from "never looked".

Hand-written (autogenerate is unreliable for this repo).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "youtube_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("comment_id", sa.String(100)),
        sa.Column("author", sa.String(255)),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("like_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("is_uploader", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("posted_at", sa.DateTime),
    )
    op.create_index(
        "ix_youtube_comments_item",
        "youtube_comments",
        ["knowledge_item_id", "rank"],
        unique=True,
    )
    op.add_column("youtube_metadata", sa.Column("comments_fetched_at", sa.DateTime))


def downgrade() -> None:
    with op.batch_alter_table("youtube_metadata") as batch:
        batch.drop_column("comments_fetched_at")
    op.drop_index("ix_youtube_comments_item", table_name="youtube_comments")
    op.drop_table("youtube_comments")
