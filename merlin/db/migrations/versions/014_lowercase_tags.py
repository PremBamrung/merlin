"""Lowercase and dedupe stored item tags

Revision ID: 014
Revises: 013
Create Date: 2026-10-15

Tags were stored with whatever casing the classifier (or a manual edit)
produced, so the same tag split into separate entries — ``oled`` 17 vs
``OLED`` 4. Writes now go through ``library.normalize_tags`` (lowercase,
strip, dedupe); this brings the existing rows in line.

Data only, no schema change. Only rows whose tags actually change are
updated; the ``knowledge_fts_update`` trigger resyncs the FTS index for each.
The normalisation is inlined (migrations don't import app code) and mirrors
``normalize_tags``.

Not reversible: the original casing isn't kept, so ``downgrade()`` is a no-op.
"""

from collections.abc import Sequence
import json

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize(tags: list) -> list[str]:
    out: list[str] = []
    for tag in tags:
        if isinstance(tag, str):
            t = tag.strip().lower()
            if t and t not in out:
                out.append(t)
    return out


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, tags FROM knowledge_items WHERE tags IS NOT NULL")
    ).fetchall()
    for item_id, raw in rows:
        try:
            tags = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(tags, list):
            continue
        cleaned = _normalize(tags)
        if cleaned != tags:
            conn.execute(
                sa.text("UPDATE knowledge_items SET tags = :tags WHERE id = :id"),
                {"tags": json.dumps(cleaned), "id": item_id},
            )


def downgrade() -> None:
    # The original casing is gone; nothing to restore.
    pass
