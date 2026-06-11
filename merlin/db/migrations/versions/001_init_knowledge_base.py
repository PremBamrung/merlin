"""Init knowledge base schema

Revision ID: 001
Revises:
Create Date: 2026-03-17

Creates the new unified schema tables:
  - knowledge_items
  - youtube_metadata
  - background_tasks
  - embeddings

The existing youtube_video_summary table is NEVER touched.
Run scripts/migrate_youtube_data.py after this to populate from the old table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(512), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("author", sa.String(255)),
        sa.Column("published_at", sa.DateTime),
        sa.Column("ingested_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("raw_content", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("summary_length", sa.String(20)),
        sa.Column("tags", sa.Text),
        sa.Column("topics", sa.Text),
        sa.Column("llm_model", sa.String(100)),
        sa.Column("word_count", sa.Integer),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text),
        sa.UniqueConstraint("source_type", "source_id", name="uq_knowledge_source"),
    )
    op.create_index("ix_knowledge_status", "knowledge_items", ["status"])
    op.create_index("ix_knowledge_ingested", "knowledge_items", ["ingested_at"])

    op.create_table(
        "youtube_metadata",
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("video_id", sa.String(20), nullable=False, unique=True),
        sa.Column("channel", sa.String(255)),
        sa.Column("views", sa.Integer),
        sa.Column("duration", sa.String(20)),
        sa.Column("subscribers", sa.String(50)),
        sa.Column("videos_count", sa.String(50)),
        sa.Column("timestamps", sa.Text),
        sa.Column("detected_language", sa.String(20)),
        sa.Column("thumbnail_url", sa.String(512)),
    )

    op.create_table(
        "background_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("message", sa.Text),
        sa.Column("input_data", sa.Text),
        sa.Column("result_data", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_tasks_status", "background_tasks", ["status"])
    op.create_index("ix_tasks_created", "background_tasks", ["created_at"])

    op.create_table(
        "embeddings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text),
        sa.Column("embedding_model", sa.String(100)),
        sa.UniqueConstraint(
            "knowledge_item_id", "chunk_index", name="uq_embedding_chunk"
        ),
    )
    op.create_index("ix_embeddings_item", "embeddings", ["knowledge_item_id"])

    # FTS5 virtual table for full-text search over knowledge_items
    # SQLite FTS5 — created via raw SQL (Alembic doesn't support virtual tables)
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
            title,
            summary,
            raw_content,
            tags,
            content=knowledge_items,
            content_rowid=rowid
        )
        """
    )

    # Triggers to keep the FTS index in sync
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert
        AFTER INSERT ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(rowid, title, summary, raw_content, tags)
            VALUES (new.rowid, new.title, new.summary, new.raw_content, new.tags);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_fts_update
        AFTER UPDATE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, summary, raw_content, tags)
            VALUES ('delete', old.rowid, old.title, old.summary, old.raw_content, old.tags);
            INSERT INTO knowledge_fts(rowid, title, summary, raw_content, tags)
            VALUES (new.rowid, new.title, new.summary, new.raw_content, new.tags);
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete
        BEFORE DELETE ON knowledge_items BEGIN
            INSERT INTO knowledge_fts(knowledge_fts, rowid, title, summary, raw_content, tags)
            VALUES ('delete', old.rowid, old.title, old.summary, old.raw_content, old.tags);
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_fts_delete")
    op.execute("DROP TRIGGER IF EXISTS knowledge_fts_update")
    op.execute("DROP TRIGGER IF EXISTS knowledge_fts_insert")
    op.execute("DROP TABLE IF EXISTS knowledge_fts")
    op.drop_table("embeddings")
    op.drop_table("background_tasks")
    op.drop_table("youtube_metadata")
    op.drop_table("knowledge_items")
