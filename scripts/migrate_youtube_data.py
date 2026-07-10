"""
One-time migration: youtube_video_summary → knowledge_items + youtube_metadata

Safe to run multiple times (idempotent via UNIQUE constraints).
The old table is never touched — it stays as a read-only backup.

Usage:
    conda run -n merlin python scripts/migrate_youtube_data.py
"""

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import sys
import uuid

DB_PATH = Path(__file__).parent.parent / "merlin.db"


def _now_iso():
    return datetime.now(UTC).isoformat()


def migrate():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Check source table exists
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "youtube_video_summary" not in tables:
        print("Source table youtube_video_summary not found — nothing to migrate.")
        conn.close()
        return

    if "knowledge_items" not in tables:
        print("ERROR: Target table knowledge_items does not exist.")
        print("Run: conda run -n merlin alembic upgrade head")
        conn.close()
        sys.exit(1)

    rows = conn.execute("SELECT * FROM youtube_video_summary").fetchall()
    print(f"Found {len(rows)} rows in youtube_video_summary")

    migrated = 0
    skipped = 0

    for row in rows:
        try:
            item_id = str(uuid.uuid4())
            video_id = row["video_id"]

            # Parse date
            published_at = None
            if row["date"]:
                try:
                    published_at = datetime.strptime(
                        str(row["date"]), "%Y-%m-%d %H:%M:%S"
                    ).isoformat()
                except Exception:
                    try:
                        published_at = datetime.strptime(
                            str(row["date"]), "%d/%m/%Y"
                        ).isoformat()
                    except Exception:
                        published_at = None

            ingested_at = None
            if row["date_added"]:
                try:
                    ingested_at = datetime.strptime(
                        str(row["date_added"]), "%Y-%m-%d %H:%M:%S"
                    ).isoformat()
                except Exception:
                    ingested_at = _now_iso()
            else:
                ingested_at = _now_iso()

            status = "completed" if row["summary"] else "pending"

            # Serialize topics (already JSON or dict)
            topics_raw = row["topics"]
            if topics_raw and not isinstance(topics_raw, str):
                topics_raw = json.dumps(topics_raw)

            tags_raw = row["tags"] or "[]"
            # Old tags are comma-separated strings — convert to JSON array
            if tags_raw and not tags_raw.startswith("["):
                tag_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
                tags_raw = json.dumps(tag_list)

            # Insert knowledge_item
            conn.execute(
                """
                INSERT OR IGNORE INTO knowledge_items
                    (id, source_type, source_id, title, author,
                     published_at, ingested_at, updated_at,
                     raw_content, summary, summary_length,
                     tags, sections, llm_model, word_count, status, error_message)
                VALUES (?, 'youtube', ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    video_id,
                    row["title"],
                    row["channel"],
                    published_at,
                    ingested_at,
                    ingested_at,
                    row["subtitles"],
                    row["summary"],
                    row["summary_length"],
                    tags_raw,
                    topics_raw,
                    row["llm_model"],
                    row["words_count"],
                    status,
                    row["error_message"],
                ),
            )

            # Check if the INSERT was ignored (row already existed)
            # If so, get the existing item's id
            existing = conn.execute(
                "SELECT id FROM knowledge_items WHERE source_type='youtube' AND source_id=?",
                (video_id,),
            ).fetchone()
            if existing:
                actual_id = existing["id"]
            else:
                actual_id = item_id

            # Parse timestamps
            timestamps_raw = row["timestamps"]
            if timestamps_raw and not isinstance(timestamps_raw, str):
                timestamps_raw = json.dumps(timestamps_raw)

            # Parse views
            views = row["views"]
            if isinstance(views, str):
                try:
                    views = int(views.replace(",", "").replace(" views", ""))
                except Exception:
                    views = None

            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

            conn.execute(
                """
                INSERT OR IGNORE INTO youtube_metadata
                    (knowledge_item_id, video_id, channel, views, duration,
                     subscribers, videos_count, timestamps, thumbnail_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actual_id,
                    video_id,
                    row["channel"],
                    views,
                    row["duration"],
                    row["subscribers"],
                    row["videos"],
                    timestamps_raw,
                    thumbnail_url,
                ),
            )

            migrated += 1

        except Exception as e:
            print(f"  SKIP video_id={row['video_id']}: {e}")
            skipped += 1

    conn.commit()

    # Rebuild FTS index for migrated rows
    print("Rebuilding FTS index…")
    try:
        conn.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")
        conn.commit()
        print("FTS index rebuilt.")
    except Exception as e:
        print(f"  FTS rebuild warning (non-fatal): {e}")

    conn.close()

    print(f"\nDone. Migrated: {migrated}, Skipped: {skipped}")
    print("Old table youtube_video_summary preserved as backup.")
    print(
        "Once verified, you can rename it: ALTER TABLE youtube_video_summary RENAME TO youtube_video_summary_backup"
    )


if __name__ == "__main__":
    migrate()
