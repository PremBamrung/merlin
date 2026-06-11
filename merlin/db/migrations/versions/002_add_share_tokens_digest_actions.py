"""Add share_tokens and digest_actions tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "share_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token", sa.String(8), nullable=False, unique=True),
        sa.Column("knowledge_item_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.ForeignKeyConstraint(["knowledge_item_id"], ["knowledge_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_share_tokens_token", "share_tokens", ["token"], unique=True)

    op.create_table(
        "digest_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("knowledge_item_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.ForeignKeyConstraint(["knowledge_item_id"], ["knowledge_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_digest_actions_item", "digest_actions", ["knowledge_item_id"])


def downgrade() -> None:
    op.drop_index("ix_digest_actions_item", table_name="digest_actions")
    op.drop_table("digest_actions")
    op.drop_index("ix_share_tokens_token", table_name="share_tokens")
    op.drop_table("share_tokens")
