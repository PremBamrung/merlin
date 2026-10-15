"""Add transcript provenance + summary language to youtube_metadata

Revision ID: 012
Revises: 011
Create Date: 2026-10-15

`detected_language` is the video's spoken language; it doesn't say which text
the summary was actually built from. These record it, so the Reader can show
"FR · auto-generated" vs "audio (Groq)" and the language the summary was
written in:

- `transcript_language` — code of the subtitle track used (e.g. "fr").
- `transcript_source` — manual | auto | audio.
- `summary_language` — language name the summary was written in ("french").

Hand-written (autogenerate is unreliable for this repo). Plain nullable ADD
COLUMNs work in SQLite without a batch rebuild. NULL = older items.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("youtube_metadata", sa.Column("transcript_language", sa.String(20)))
    op.add_column("youtube_metadata", sa.Column("transcript_source", sa.String(10)))
    op.add_column("youtube_metadata", sa.Column("summary_language", sa.String(30)))


def downgrade() -> None:
    with op.batch_alter_table("youtube_metadata") as batch:
        batch.drop_column("summary_language")
        batch.drop_column("transcript_source")
        batch.drop_column("transcript_language")
