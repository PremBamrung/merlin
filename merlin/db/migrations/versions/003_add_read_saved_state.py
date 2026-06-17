"""Add read_at / saved_at consumption state to knowledge_items

Revision ID: 003
Revises: 002
Create Date: 2026-06-17

Adds the Feed's read/saved state as two nullable timestamps:
  - read_at  : NULL ⇔ unread (the swipe-to-read queue filters on this)
  - saved_at : the ★ bookmark flag (doubles as save order)

Hand-written (autogenerate is unreliable for this repo). No FTS/trigger
changes — neither column is searched. Plain ADD COLUMN works in SQLite for
nullable columns, so no batch rebuild is needed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_items", sa.Column("read_at", sa.DateTime, nullable=True))
    op.add_column("knowledge_items", sa.Column("saved_at", sa.DateTime, nullable=True))
    op.create_index("ix_knowledge_read", "knowledge_items", ["read_at"])
    op.create_index("ix_knowledge_saved", "knowledge_items", ["saved_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_saved", table_name="knowledge_items")
    op.drop_index("ix_knowledge_read", table_name="knowledge_items")
    op.drop_column("knowledge_items", "saved_at")
    op.drop_column("knowledge_items", "read_at")
