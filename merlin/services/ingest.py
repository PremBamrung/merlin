"""
Ingestion service — submit YouTube URLs for background processing and inspect
task progress. Wraps the plugin registry + task queue so the UI stays thin.

`persist_result` is the `on_complete` callback (moved verbatim from the old
FastAPI `sources/youtube.py` router); it upserts the knowledge item + YouTube
metadata and marks the task completed.
"""

from datetime import UTC, datetime
import json
import uuid

from merlin.config import settings
from merlin.core.task_queue import task_queue
from merlin.db.engine import SessionFactory
from merlin.db.models import KnowledgeItem
from merlin.db.repositories.knowledge import (
    KnowledgeItemRepository,
    YouTubeMetadataRepository,
)
from merlin.db.repositories.tasks import BackgroundTaskRepository
from merlin.knowledge_sources.plugins.youtube.extractors import VideoExtractor
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

    If the video is already in the library (with a stored transcript), this
    skips the full pipeline — no metadata fetch, no subtitle/audio download —
    and re-summarises from the saved transcript instead.

    Raises ValueError if the plugin is unavailable or input is invalid.
    """
    plugin = registry.get("youtube")
    if not plugin:
        raise ValueError("YouTube plugin not registered")

    options = {"languages": languages or ["en"], "summary_length": summary_length}
    errors = plugin.validate_input(url, options)
    if errors:
        raise ValueError("; ".join(errors))

    # Already ingested? Re-summarise from the stored transcript rather than
    # re-running extraction (metadata + subs are already saved).
    video_id = VideoExtractor.extract_video_id(url)
    if video_id:
        with SessionFactory() as session:
            existing = KnowledgeItemRepository.get_by_source(
                session, "youtube", video_id
            )
            existing_id = existing.id if existing and existing.raw_content else None
        if existing_id:
            return resummarize(existing_id, summary_length, languages)

    return task_queue.submit_ingest(
        plugin=plugin,
        raw_input=url,
        options=options,
        on_complete=persist_result,
    )


def resummarize(
    item_id: str,
    summary_length: str | None = None,
    languages: list[str] | None = None,
) -> str:
    """Re-summarise an existing item from its stored transcript (no network).

    Reuses the saved `raw_content` + YouTube metadata and only re-runs the
    summariser, then bumps `ingested_at` so the refreshed item surfaces at the
    top of the "Newest" sort. Returns a task_id to poll, like `submit_youtube`.
    """

    def work(task_id: str, report) -> None:
        report(10, "Loading stored transcript…")
        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item:
                raise ValueError("Item not found")
            raw_text = item.raw_content
            title = item.title
            channel = item.author
            meta = item.youtube_metadata
            detected = (meta.detected_language if meta else "") or ""
            length = summary_length or item.summary_length or "short"
        if not raw_text:
            raise ValueError("No stored transcript to re-summarise")

        report(40, "Generating summary…")
        plugin = registry.get("youtube")
        if not plugin:
            raise ValueError("YouTube plugin not registered")
        summary, topics, timestamps = plugin.resummarize(
            raw_text=raw_text,
            title=title,
            channel=channel,
            detected_language=detected,
            user_languages=languages or ["en"],
            summary_length=length,
        )

        report(90, "Saving to knowledge base…")
        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item:
                raise ValueError("Item not found")
            item.summary = summary
            item.summary_length = length
            item.topics = json.dumps(topics)
            item.llm_model = settings.llm_model_name
            item.status = "completed"
            item.error_message = None
            item.ingested_at = datetime.now(UTC)  # bump to top of "Newest"
            if item.youtube_metadata is not None:
                item.youtube_metadata.timestamps = json.dumps(timestamps)
            BackgroundTaskRepository.set_completed(
                session,
                task_id,
                {"knowledge_item_id": item_id},
                knowledge_item_id=item_id,
            )
            session.commit()

    return task_queue.submit_callable(
        work,
        task_type="resummarize_youtube",
        input_data={"item_id": item_id, "summary_length": summary_length},
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

    When the transcript is already stored this re-summarises in place; only if
    it's missing do we fall back to a full re-ingest from YouTube.
    """
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if not item or item.source_type != "youtube":
            raise ValueError("Item not found")
        has_transcript = bool(item.raw_content)
        meta = item.youtube_metadata
        video_id = meta.video_id if meta else None
        detected = (meta.detected_language or "").split("-")[0] if meta else None
        summary_length = summary_length or item.summary_length or "short"

    langs = languages or [lang for lang in (detected, "en") if lang]

    if has_transcript:
        return resummarize(item_id, summary_length, langs)

    if not video_id:
        raise ValueError("No YouTube metadata found")
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
