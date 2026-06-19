"""Fixtures for the FastAPI backend tests.

These tests exercise the real router → `merlin.services` → SQLite path against
an **isolated temp database** built by the **real Alembic migrations** (so the
FTS5 virtual table + triggers exist exactly as in prod). Only the network/LLM
boundaries are monkeypatched per-test — the DB path is genuine.

`DATABASE_URL` must point at the temp file *before* `merlin.config` is first
imported (it builds a module-level `settings` singleton and a bound engine), so
it is set here at import time, before any `api`/`merlin` import.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import uuid

import pytest

# --- point the core library at a throwaway DB BEFORE importing it ----------- #
_TMP_DIR = Path(tempfile.mkdtemp(prefix="merlin-test-"))
_DB_PATH = _TMP_DIR / "test.db"
import os  # noqa: E402

os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
# Plain rollback journal — no WAL sidecar files for a short-lived test DB.
os.environ["SQLITE_JOURNAL_MODE"] = "DELETE"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _migrate_temp_db():
    """Create the full schema (tables + FTS triggers) via Alembic, once."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def client(_migrate_temp_db):
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_tables(_migrate_temp_db):
    """Truncate item/task tables between tests for isolation."""
    yield
    from sqlalchemy import text

    from merlin.db.engine import engine

    with engine.begin() as conn:
        # Children/related first; the FTS triggers keep knowledge_fts in sync.
        for table in (
            "background_tasks",
            "youtube_metadata",
            "embeddings",
            "knowledge_items",
        ):
            conn.execute(text(f"DELETE FROM {table}"))


@pytest.fixture
def make_item():
    """Factory inserting a completed KnowledgeItem (+ YouTube metadata).

    Returns the new item id; accepts overrides for the columns tests assert on.
    """

    def _make(**overrides) -> str:
        from merlin.db.engine import SessionFactory
        from merlin.db.models import KnowledgeItem, YouTubeMetadata

        item_id = overrides.pop("id", str(uuid.uuid4()))
        video_id = overrides.pop("source_id", f"vid_{item_id[:8]}")
        tags = overrides.pop("tags", ["ai", "python"])
        topics = overrides.pop("topics", {"Overview": "00:00:00"})
        timestamps = overrides.pop("timestamps", {"Overview": 0})
        channel = overrides.pop("channel", "Test Channel")
        description = overrides.pop("description", None)

        item = KnowledgeItem(
            id=item_id,
            source_type=overrides.pop("source_type", "youtube"),
            source_id=video_id,
            title=overrides.pop("title", "Test Video"),
            author=overrides.pop("author", channel),
            summary=overrides.pop("summary", "A test summary about transformers."),
            summary_length=overrides.pop("summary_length", "short"),
            raw_content=overrides.pop("raw_content", "Full transcript text here."),
            tags=json.dumps(tags),
            topics=json.dumps(topics),
            word_count=overrides.pop("word_count", 1944),
            llm_model=overrides.pop("llm_model", "deepseek/test"),
            status=overrides.pop("status", "completed"),
            error_message=overrides.pop("error_message", None),
        )
        for key, value in overrides.items():
            setattr(item, key, value)

        with SessionFactory() as session:
            session.add(item)
            session.flush()
            session.add(
                YouTubeMetadata(
                    knowledge_item_id=item.id,
                    video_id=video_id,
                    channel=channel,
                    views=12345,
                    duration="00:16:59",
                    subscribers="1.2M",
                    videos_count="803",
                    thumbnail_url="https://img.example/thumb.jpg",
                    detected_language="en",
                    description=description,
                    timestamps=json.dumps(timestamps),
                )
            )
            session.commit()
        return item_id

    return _make


@pytest.fixture
def make_task():
    """Factory inserting a background_tasks row; returns the task id."""

    def _make(**overrides) -> str:
        from merlin.db.engine import SessionFactory
        from merlin.db.models import BackgroundTask

        task_id = overrides.pop("id", str(uuid.uuid4()))
        task = BackgroundTask(
            id=task_id,
            task_type=overrides.pop("task_type", "ingest_youtube"),
            status=overrides.pop("status", "processing"),
            progress=overrides.pop("progress", 62),
            message=overrides.pop("message", "Downloading audio…"),
            input_data=json.dumps(overrides.pop("input_data", {"raw_input": "url"})),
            result_data=overrides.pop("result_data", None),
            error=overrides.pop("error", None),
            knowledge_item_id=overrides.pop("knowledge_item_id", None),
        )
        for key, value in overrides.items():
            setattr(task, key, value)

        with SessionFactory() as session:
            session.add(task)
            session.commit()
        return task_id

    return _make
