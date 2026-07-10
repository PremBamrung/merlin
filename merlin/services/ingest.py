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
from merlin.core.logging import logger
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

# Supported summary lengths. "medium" was retired; legacy items may still have
# it stored, so normalise any unsupported value back to "short".
_SUMMARY_LENGTHS = ("short", "long")


def _normalize_summary_length(length: str | None) -> str:
    """Coerce a (possibly legacy/None) summary length to a supported value."""
    return length if length in _SUMMARY_LENGTHS else "short"


def _missing_youtube_fields(meta) -> list[str]:
    """Self-heal gap list: which grounding fields the stored metadata lacks.

    Old items predate fields we add later (e.g. `description`). The redo path
    does a cheap, metadata-only fetch when this is non-empty, so re-summarising
    an old item backfills whatever a newer feature needs. Add new fields here as
    they're introduced — that's all it takes for old items to self-heal.
    """
    if meta is None:
        return ["description"]
    checks = {"description": meta.description}
    return [k for k, v in checks.items() if v in (None, "")]


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
            "sections": json.dumps(result.sections),
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
        item_id = item.id  # capture before commit expires the instance
        session.commit()

    _record_ingest_usage(item_id, result)
    # Classify BEFORE embedding: the classifier is what writes real tags now
    # (the plugin emits tags=[]), and the item vector is built from
    # title+tags+summary. Embedding first would bake in empty tags permanently
    # (heal_missing_embeddings never revisits an item that already has a vector).
    _classify(item_id)
    _index_for_search(item_id)


def _record_ingest_usage(item_id: str, result) -> None:
    """Write the summarize (+ transcribe, if audio was used) llm_usage rows for a
    finished ingest. Visibility only; `usage.record` swallows its own errors."""
    from merlin.services import usage

    if (
        result.summarize_input_tokens is not None
        or result.summarize_output_tokens is not None
        or result.summarize_cost_usd is not None
    ):
        usage.record(
            surface="summarize",
            provider=settings.llm_provider,
            model=result.llm_model,
            input_tokens=result.summarize_input_tokens,
            output_tokens=result.summarize_output_tokens,
            cost_usd=result.summarize_cost_usd,
            knowledge_item_id=item_id,
        )
    if result.transcribe_audio_seconds:
        usage.record(
            surface="transcribe",
            provider="groq",
            model=result.transcribe_model,
            audio_seconds=result.transcribe_audio_seconds,
            knowledge_item_id=item_id,
        )


def _classify(item_id: str) -> None:
    """Best-effort topic + tag classification (see services.classify). Swallows
    its own errors so it can never fail an otherwise-successful ingest."""
    from merlin.services import classify

    classify.classify_and_persist(item_id)


def _index_for_search(item_id: str) -> None:
    """Best-effort: embed the item for semantic search after a successful ingest.

    Re-reads title/summary/tags from the DB (not the IngestResult) so it embeds
    with the tags the classifier just wrote — must run AFTER `_classify`.

    Inert under `NullEmbedder` (EMBEDDING_PROVIDER=none). A Jina failure is
    logged and swallowed — it must never fail an otherwise-successful ingest;
    the backfill script can pick the item up later.
    """
    try:
        from merlin.rag.embeddings import get_embedder, store_item_embedding

        if not get_embedder().enabled:
            return
        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item:
                return
            tags = _parse_json(item.tags, []) or []
            if store_item_embedding(
                session,
                item_id=item_id,
                title=item.title,
                summary=item.summary,
                tags=tags,
            ):
                session.commit()
    except Exception:
        logger.warning("Embedding index failed for item %s", item_id, exc_info=True)


# ------------------------------------------------------------------
# Public service API (called by the UI)
# ------------------------------------------------------------------


def submit_youtube(
    url: str,
    languages: list[str],
    summary_length: str = "short",
    force: bool = False,
) -> dict:
    """Validate and enqueue a YouTube ingest.

    Returns one of two dict shapes:

    * ``{"status": "started", "task_id": <id>}`` — a fresh ingest (or, with
      ``force=True``, a re-summarise) was queued; poll the task to track it.
    * ``{"status": "exists", "item_id": <id>, "title": <title>}`` — the video
      is already in the library with a stored transcript and ``force`` is False,
      so nothing was queued. The caller should confirm with the user before
      re-summarising (via ``resummarize`` / the resummarize endpoint).

    Pass ``force=True`` to skip the confirmation gate and re-summarise an
    already-ingested video in place (used by retry/digest, which always proceed).

    Raises ValueError if the plugin is unavailable or input is invalid.
    """
    plugin = registry.get("youtube")
    if not plugin:
        raise ValueError("YouTube plugin not registered")

    options = {
        "languages": languages or ["en", "fr"],
        "summary_length": summary_length,
    }
    errors = plugin.validate_input(url, options)
    if errors:
        raise ValueError("; ".join(errors))

    # Already ingested? Don't silently re-summarise — surface it so the caller
    # can ask the user first. With force=True (retry/digest, or a confirmed
    # redo) re-summarise from the stored transcript instead of re-extracting.
    video_id = VideoExtractor.extract_video_id(url)
    if video_id:
        with SessionFactory() as session:
            existing = KnowledgeItemRepository.get_by_source(
                session, "youtube", video_id
            )
            existing_id = existing.id if existing and existing.raw_content else None
            existing_title = existing.title if existing else None
        if existing_id:
            if not force:
                return {
                    "status": "exists",
                    "item_id": existing_id,
                    "title": existing_title,
                }
            return {
                "status": "started",
                "task_id": resummarize(existing_id, summary_length, languages),
            }

    task_id = task_queue.submit_ingest(
        plugin=plugin,
        raw_input=url,
        options=options,
        on_complete=persist_result,
    )
    return {"status": "started", "task_id": task_id}


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
            video_id = meta.video_id if meta else None
            description = (meta.description if meta else None) or ""
            missing = _missing_youtube_fields(meta)
            length = _normalize_summary_length(summary_length or item.summary_length)
            # Title is known up front here — surface it on the task row right away.
            BackgroundTaskRepository.set_title(session, task_id, title)
            session.commit()
        if not raw_text:
            raise ValueError("No stored transcript to re-summarise")

        # Self-heal: if the stored metadata is missing grounding fields a newer
        # feature needs (e.g. description), do ONE cheap metadata-only fetch —
        # no subtitle/audio re-download — and fill just the gaps. Degrade
        # gracefully: a failed fetch never blocks the re-summarise.
        healed: dict[str, str] = {}
        if missing and video_id:
            report(25, "Fetching missing video details…")
            try:
                url = f"https://www.youtube.com/watch?v={video_id}"
                info = VideoExtractor.extract_video_info(url) or {}
            except Exception as exc:  # pragma: no cover - network failure path
                logger.warning(
                    "Self-heal metadata fetch failed for %s: %s", video_id, exc
                )
                info = {}
            field_sources = {"description": info.get("description", "")}
            for field in missing:
                value = field_sources.get(field)
                if value:
                    healed[field] = value
            description = healed.get("description") or description

        report(40, "Generating summary…")
        plugin = registry.get("youtube")
        if not plugin:
            raise ValueError("YouTube plugin not registered")
        # Default to the languages the user understands, seeded with the
        # video's own detected language so a re-summarise of a French video
        # reads in French rather than falling back to English.
        langs = languages or [
            lang for lang in (detected.split("-")[0].lower(), "en", "fr") if lang
        ]
        summary, sections, timestamps = plugin.resummarize(
            raw_text=raw_text,
            title=title,
            channel=channel,
            detected_language=detected,
            user_languages=langs,
            summary_length=length,
            description=description,
        )
        summ_usage = getattr(plugin.summarizer, "last_usage", None) or {}

        report(90, "Saving to knowledge base…")
        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item:
                raise ValueError("Item not found")
            item.summary = summary
            item.summary_length = length
            item.sections = json.dumps(sections)
            item.llm_model = settings.llm_model_name
            item.status = "completed"
            item.error_message = None
            item.ingested_at = datetime.now(UTC)  # bump to top of "Newest"
            if item.youtube_metadata is not None:
                item.youtube_metadata.timestamps = json.dumps(timestamps)
                # Persist any fields filled by the self-heal fetch above.
                for field, value in healed.items():
                    setattr(item.youtube_metadata, field, value)
            BackgroundTaskRepository.set_completed(
                session,
                task_id,
                {"knowledge_item_id": item_id},
                knowledge_item_id=item_id,
            )
            session.commit()

        if summ_usage:
            from merlin.services import usage

            usage.record(
                surface="summarize",
                provider=settings.llm_provider,
                model=settings.llm_model_name,
                input_tokens=summ_usage.get("input_tokens"),
                output_tokens=summ_usage.get("output_tokens"),
                cost_usd=summ_usage.get("cost_usd"),
                knowledge_item_id=item_id,
            )

        # Re-classify (refreshes topics; leaves user-assigned rows + existing
        # tags untouched) then re-embed. Re-summarise previously left a stale
        # vector — same classify-then-embed order as the fresh ingest path.
        _classify(item_id)
        _index_for_search(item_id)

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
        summary_length = _normalize_summary_length(
            summary_length or item.summary_length
        )

    langs = languages or [lang for lang in (detected, "en") if lang]

    if has_transcript:
        return resummarize(item_id, summary_length, langs)

    if not video_id:
        raise ValueError("No YouTube metadata found")
    url = f"https://www.youtube.com/watch?v={video_id}"
    # A retry always proceeds — force past the already-ingested confirmation
    # gate. (No transcript here anyway, so this hits the fresh-ingest path.)
    return submit_youtube(url, langs, summary_length, force=True)["task_id"]


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
        "title": task.title,
        "source_input": _parse_json(task.input_data, {}).get("raw_input"),
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


def cancel_task(task_id: str) -> bool:
    """Request cancellation of an in-flight ingest/re-summarise task.

    Cooperative: a still-queued task is marked cancelled immediately; a running
    one stops at its next progress checkpoint (blocking work already in flight —
    e.g. an LLM call — finishes first). Returns False if the task is unknown or
    already in a terminal state (nothing to cancel).
    """
    return task_queue.cancel(task_id)


def _parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
