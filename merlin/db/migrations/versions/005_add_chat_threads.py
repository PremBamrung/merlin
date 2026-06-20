"""Add chat_threads + chat_messages (continuable chat history)

Revision ID: 005
Revises: 004
Create Date: 2026-06-20

Persists the library-wide `/chat` conversations so they can be reopened and
continued. Each turn (user + assistant) is stored as a `chat_messages` row whose
`parts` column holds the **Vercel AI SDK `UIMessage` parts** verbatim (text,
reasoning, tool calls/results, and our custom citation data-parts) as JSON — so a
reopened thread renders exactly as it did live and replays cleanly as agent
history on continuation.

Plain `create_table` (no FTS/triggers), so this is one of the few migrations
where autogenerate would have been fine; still hand-written for consistency.
Cascade-delete drops a thread's messages with it. The Reader per-item chat stays
ephemeral and never writes here.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        # NULL until the title call returns; the UI falls back to a preview.
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        # Bumped on every saved turn; the sidebar sorts by this, newest first.
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_chat_threads_updated", "chat_threads", ["updated_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),  # order within the thread
        sa.Column("role", sa.String(20), nullable=False),  # 'user' | 'assistant'
        sa.Column("parts", sa.Text, nullable=True),  # JSON: UIMessage parts
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_chat_messages_thread_seq", "chat_messages", ["thread_id", "seq"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_thread_seq", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_updated", table_name="chat_threads")
    op.drop_table("chat_threads")
