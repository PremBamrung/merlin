"""
Ingestion service — submit YouTube URLs for background processing and inspect
task progress. Wraps the plugin registry + task queue so the UI stays thin.

`persist_result` is the `on_complete` callback (moved verbatim from the old
FastAPI `sources/youtube.py` router); it upserts the knowledge item + YouTube
metadata and marks the task completed.
"""

import json
import uuid

from merlin.core.task_queue import task_queue
from merlin.db.engine import SessionFactory
from merlin.db.models import KnowledgeItem
from merlin.db.repositories.knowledge import (
    KnowledgeItemRepository,
    YouTubeMetadataRepository,
)
from merlin.db.repositories.tasks import BackgroundTaskRepository
from merlin.knowledge_sources.registry import registry

# ------------------------------------------------------------------
# on_complete callback — runs in the worker thread after a successful ingest
# ------------------------------------------------------------------


def persist_result(task_id: str, result) -> None:
    """Persist an IngestResult to the DB and mark the task completed."""
    with SessionFactory() as session:
        existing = KnowledgeItemRepository.get_by_source(
            session, result.source_type, result.source_id
        )

        item_data = {
            "source_type": result.source_type,
            "source_id": result.source_id,
            "title": result.title,
            "author": result.author,
            "published_at": result.published_at,
            "raw_content": result.raw_content,
            "summary": result.summary,
            "summary_length": result.summary_length,
            "tags": json.dumps(result.tags),
            "topics": json.dumps(result.topics),
            "llm_model": result.llm_model,
            "word_count": result.word_count,
            "status": "completed",
            "error_message": None,
        }

        if existing:
            for k, v in item_data.items():
                setattr(existing, k, v)
            item = existing
        else:
            item = KnowledgeItem(id=str(uuid.uuid4()), **item_data)
            session.add(item)
            session.flush()

        YouTubeMetadataRepository.upsert(session, item.id, result.source_metadata)

        BackgroundTaskRepository.set_completed(
            session, task_id, {"knowledge_item_id": item.id}, knowledge_item_id=item.id
        )
        session.commit()


# ------------------------------------------------------------------
# Public service API (called by the UI)
# ------------------------------------------------------------------


def submit_youtube(
    url: str,
    languages: list[str],
    summary_length: str = "short",
) -> str:
    """Validate and enqueue a YouTube ingest. Returns the task_id to poll.

    Raises ValueError if the plugin is unavailable or input is invalid.
    """
    plugin = registry.get("youtube")
    if not plugin:
        raise ValueError("YouTube plugin not registered")

    options = {"languages": languages or ["en"], "summary_length": summary_length}
    errors = plugin.validate_input(url, options)
    if errors:
        raise ValueError("; ".join(errors))

    return task_queue.submit_ingest(
        plugin=plugin,
        raw_input=url,
        options=options,
        on_complete=persist_result,
    )


def retry(
    item_id: str,
    languages: list[str] | None = None,
    summary_length: str | None = None,
) -> str:
    """Re-ingest an existing item by reconstructing its URL from the video id.

    Unlike the old API (which hardcoded ["en", "fr"]), the caller may pass the
    desired languages and/or a new summary length; languages default to the
    item's detected language then English, and length to the item's current.
    """
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if not item or item.source_type != "youtube":
            raise ValueError("Item not found")
        meta = item.youtube_metadata
        if not meta:
            raise ValueError("No YouTube metadata found")
        video_id = meta.video_id
        detected = (meta.detected_language or "").split("-")[0] or None
        summary_length = summary_length or item.summary_length or "short"

    langs = languages or [lang for lang in (detected, "en") if lang]
    url = f"https://www.youtube.com/watch?v={video_id}"
    return submit_youtube(url, langs, summary_length)


# ------------------------------------------------------------------
# Task inspection
# ------------------------------------------------------------------


def _serialize_task(task) -> dict:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress or 0,
        "message": task.message,
        "error": task.error,
        "knowledge_item_id": task.knowledge_item_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "result_data": _parse_json(task.result_data, None),
    }


def recent_tasks(limit: int = 10) -> list[dict]:
    with SessionFactory() as session:
        return [
            _serialize_task(t)
            for t in BackgroundTaskRepository.list_recent(session, limit=limit)
        ]


def get_task(task_id: str) -> dict | None:
    with SessionFactory() as session:
        task = BackgroundTaskRepository.get(session, task_id)
        return _serialize_task(task) if task else None


def _parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
