"""Denormalize chat_threads.message_count + preview

Revision ID: 006
Revises: 005
Create Date: 2026-06-24

The chat-history sidebar (GET /api/chat/threads) used to load every message of
every thread just to compute a message count and a first-user-message preview —
an N+1 over potentially large `parts` JSON blobs, run on every turn (the list is
refetched whenever a thread is saved). These two columns let `list_threads` read
one row per thread instead; they're refreshed on every `save_thread`. Here we add
them and backfill existing rows from their messages.
"""

from collections.abc import Sequence
import json

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirror chat_history._PREVIEW_CHARS (kept inline so the migration is
# self-contained — it must not import app code that may change later).
_PREVIEW_CHARS = 140


def _first_user_preview(rows: Sequence) -> str | None:
    """First user message's concatenated text parts, capped — mirrors
    chat_history._first_user_text. `rows` is (role, parts_json) ordered by seq."""
    for role, parts_json in rows:
        if role != "user":
            continue
        try:
            parts = json.loads(parts_json or "[]")
        except (TypeError, ValueError):
            continue
        text = " ".join(
            p.get("text", "")
            for p in parts
            if isinstance(p, dict) and p.get("type") == "text"
        ).strip()
        if text:
            return text[:_PREVIEW_CHARS] or None
    return None


def upgrade() -> None:
    op.add_column(
        "chat_threads", sa.Column("message_count", sa.Integer, nullable=True)
    )
    op.add_column(
        "chat_threads", sa.Column("preview", sa.String(512), nullable=True)
    )

    # Backfill from existing messages so reopened threads show counts/previews
    # without waiting for their next save.
    conn = op.get_bind()
    thread_ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM chat_threads"))]
    for tid in thread_ids:
        rows = conn.execute(
            sa.text(
                "SELECT role, parts FROM chat_messages "
                "WHERE thread_id = :tid ORDER BY seq"
            ),
            {"tid": tid},
        ).fetchall()
        conn.execute(
            sa.text(
                "UPDATE chat_threads SET message_count = :c, preview = :p "
                "WHERE id = :tid"
            ),
            {"c": len(rows), "p": _first_user_preview(rows), "tid": tid},
        )


def downgrade() -> None:
    # Batch mode for SQLite column drops (matches the project's migration style).
    with op.batch_alter_table("chat_threads") as batch_op:
        batch_op.drop_column("preview")
        batch_op.drop_column("message_count")
