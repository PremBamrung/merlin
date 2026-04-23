"""
POST /api/sources/youtube  — submit a YouTube URL for ingestion
GET  /api/sources/youtube  — list all YouTube items
GET  /api/sources/youtube/{id}   — full item detail
POST /api/sources/youtube/{id}/retry        — retry failed ingestion
DELETE /api/sources/youtube/{id}/summary    — clear summary, keep subtitles
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.models import KnowledgeItem, YouTubeMetadata
from backend.db.repositories.knowledge import KnowledgeItemRepository, YouTubeMetadataRepository
from backend.db.repositories.tasks import BackgroundTaskRepository
from backend.knowledge_sources.registry import registry
from backend.core.task_queue import task_queue

router = APIRouter(prefix="/sources/youtube", tags=["youtube"])


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------

class YouTubeIngestRequest(BaseModel):
    url: str
    languages: list[str] = ["en"]
    summary_length: str = "medium"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    knowledge_item_id: Optional[str] = None


# ------------------------------------------------------------------
# on_complete callback — runs in worker thread after successful ingest
# ------------------------------------------------------------------

def _persist_result(task_id: str, result) -> None:
    """Persist IngestResult to DB and mark task completed."""
    from backend.db.engine import SessionFactory
    import uuid

    with SessionFactory() as session:
        # Upsert knowledge_item
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

        # Upsert YouTube-specific metadata
        YouTubeMetadataRepository.upsert(session, item.id, result.source_metadata)

        # Complete the task
        BackgroundTaskRepository.set_completed(
            session, task_id, {"knowledge_item_id": item.id}, knowledge_item_id=item.id
        )
        session.commit()


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@router.post("", response_model=TaskResponse)
async def ingest_youtube(body: YouTubeIngestRequest):
    """Submit a YouTube URL for background processing. Returns task_id to poll."""
    plugin = registry.get("youtube")
    if not plugin:
        raise HTTPException(status_code=500, detail="YouTube plugin not registered")

    errors = plugin.validate_input(body.url, body.model_dump())
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    task_id = await task_queue.enqueue_ingest(
        plugin=plugin,
        raw_input=body.url,
        options={"languages": body.languages, "summary_length": body.summary_length},
        on_complete=_persist_result,
    )
    return TaskResponse(task_id=task_id, status="queued")


@router.get("")
def list_youtube(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    db: Session = Depends(get_db_session),
):
    items, total = KnowledgeItemRepository.list_all(
        db, source_type="youtube", search=search, page=page, page_size=page_size
    )
    return {
        "items": [_serialize(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{item_id}")
def get_youtube_item(item_id: str, db: Session = Depends(get_db_session)):
    item = KnowledgeItemRepository.get_by_id(db, item_id)
    if not item or item.source_type != "youtube":
        raise HTTPException(status_code=404, detail="Item not found")
    return _serialize(item, include_content=True)


@router.post("/{item_id}/retry")
async def retry_youtube(item_id: str, db: Session = Depends(get_db_session)):
    item = KnowledgeItemRepository.get_by_id(db, item_id)
    if not item or item.source_type != "youtube":
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status not in ("failed", "pending"):
        raise HTTPException(status_code=409, detail=f"Cannot retry item with status '{item.status}'")

    # Reconstruct URL from video_id
    meta = item.youtube_metadata
    if not meta:
        raise HTTPException(status_code=400, detail="No YouTube metadata found")

    plugin = registry.get("youtube")
    url = f"https://www.youtube.com/watch?v={meta.video_id}"
    task_id = await task_queue.enqueue_ingest(
        plugin=plugin,
        raw_input=url,
        options={"languages": ["en"], "summary_length": item.summary_length or "medium"},
        on_complete=_persist_result,
    )
    return TaskResponse(task_id=task_id, status="queued")


@router.delete("/{item_id}/summary")
def clear_summary(item_id: str, db: Session = Depends(get_db_session)):
    """Delete just the summary fields — keeps transcript for re-summarisation."""
    ok = KnowledgeItemRepository.clear_summary(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


# ------------------------------------------------------------------
# Serializer
# ------------------------------------------------------------------

def _serialize(item: KnowledgeItem, include_content: bool = False) -> dict:
    meta = item.youtube_metadata
    d = {
        "id": item.id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "title": item.title,
        "author": item.author,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "ingested_at": item.ingested_at.isoformat() if item.ingested_at else None,
        "summary": item.summary,
        "summary_length": item.summary_length,
        "tags": _parse_json(item.tags, []),
        "topics": _parse_json(item.topics, {}),
        "llm_model": item.llm_model,
        "word_count": item.word_count,
        "status": item.status,
        "error_message": item.error_message,
        # YouTube-specific
        "channel": meta.channel if meta else None,
        "views": meta.views if meta else None,
        "duration": meta.duration if meta else None,
        "subscribers": meta.subscribers if meta else None,
        "videos_count": meta.videos_count if meta else None,
        "thumbnail_url": meta.thumbnail_url if meta else None,
        "detected_language": meta.detected_language if meta else None,
        "timestamps": _parse_json(meta.timestamps, {}) if meta else {},
    }
    if include_content:
        d["raw_content"] = item.raw_content
    return d


def _parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
