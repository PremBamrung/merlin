"""Add cache_read_tokens to llm_usage

Revision ID: 011
Revises: 010
Create Date: 2026-07-15

Persists the cached subset of a call's input tokens (the portion billed at the
provider's discounted cache-read rate). It was previously computed for pricing
but discarded, so a stored row's cost couldn't be reproduced from its columns —
a recompute or backfill had to bill cached tokens at the full input rate. Chat
also stashed it in `meta`; this makes it a first-class, queryable column for
every surface.

Hand-written (autogenerate is unreliable for this repo). Plain nullable ADD
COLUMN works in SQLite without a batch rebuild. NULL = not measured (older rows).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "llm_usage", sa.Column("cache_read_tokens", sa.Integer, nullable=True)
    )


def downgrade() -> None:
    op.drop_column("llm_usage", "cache_read_tokens")
