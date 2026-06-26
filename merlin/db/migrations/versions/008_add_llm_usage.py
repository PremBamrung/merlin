"""Add llm_usage (token/cost tracking — visibility only)

Revision ID: 008
Revises: 007
Create Date: 2026-06-25

Records every LLM / transcription call's usage so spend is *visible* in Insights.
One row per call, attributed to a surface ('chat' | 'summarize' | 'transcribe')
+ provider + model, with the token (or audio-second) counts and a computed (or
provider-reported) USD cost. NOTHING in the app rejects or throttles on spend —
this table is read-only reporting; the chat `UsageLimits(request_limit=…)` loop
guard is the only cap and it is unrelated to this.

Plain `create_table` (no FTS/triggers), so autogenerate would have been fine;
hand-written for consistency with the other migrations. `knowledge_item_id` is
nullable with ON DELETE SET NULL so deleting an item keeps its historical spend
rows (just detached) rather than vanishing the cost record.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column(
            "surface", sa.String(20), nullable=False
        ),  # chat|summarize|transcribe
        sa.Column("provider", sa.String(20), nullable=True),  # openrouter|azure|groq
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("audio_seconds", sa.Float, nullable=True),
        sa.Column(
            "requests", sa.Integer, nullable=True
        ),  # model round-trips (tool loop)
        # Actual (provider-reported) or computed from the pricing map; NULL when
        # the model is unknown — Insights shows "unknown", never a fabricated $0.
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column(
            "knowledge_item_id",
            sa.String(36),
            sa.ForeignKey("knowledge_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("meta", sa.Text, nullable=True),  # JSON: cache tokens, tool_calls…
    )
    op.create_index("ix_llm_usage_created", "llm_usage", ["created_at"])
    op.create_index("ix_llm_usage_surface", "llm_usage", ["surface"])
    op.create_index("ix_llm_usage_item", "llm_usage", ["knowledge_item_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_item", table_name="llm_usage")
    op.drop_index("ix_llm_usage_surface", table_name="llm_usage")
    op.drop_index("ix_llm_usage_created", table_name="llm_usage")
    op.drop_table("llm_usage")
