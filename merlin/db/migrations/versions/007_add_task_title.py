"""Add title to background_tasks

Revision ID: 007
Revises: 006
Create Date: 2026-06-24

Stores the document title on the ingest task so the Today page can show *which*
document is being ingested, not just the pipeline state. The title only becomes
known partway through ingestion (e.g. after YouTube metadata is fetched), so it
starts NULL and is filled in mid-flight by the plugin via request.set_title().
The submitted URL (in input_data) is the fallback shown until then.

Hand-written (autogenerate is unreliable for this repo). Not added to FTS — the
task title is transient ingest state, not searchable content. Plain nullable
ADD COLUMN works in SQLite without a batch rebuild.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("background_tasks", sa.Column("title", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("background_tasks", "title")
