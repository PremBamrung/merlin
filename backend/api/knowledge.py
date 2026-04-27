"""
GET    /api/knowledge        — paginated, filterable list
GET    /api/knowledge/{id}   — full item
PATCH  /api/knowledge/{id}   — update tags / notes
DELETE /api/knowledge/{id}   — delete item
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.repositories.knowledge import KnowledgeItemRepository

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeItemUpdate(BaseModel):
    tags: Optional[list[str]] = None
    title: Optional[str] = None


@router.get("")
def list_knowledge(
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    tags: Optional[str] = None,   # comma-separated
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db_session),
):
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    items, total = KnowledgeItemRepository.list_all(
        db,
        source_type=source_type,
        status=status,
        search=search,
        tags=tag_list,
        page=page,
        page_size=per_page,
    )
    return {
        "items": [_serialize(item) for item in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{item_id}")
def get_knowledge_item(item_id: str, db: Session = Depends(get_db_session)):
    item = KnowledgeItemRepository.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return _serialize(item, include_content=True)


@router.patch("/{item_id}")
def update_knowledge_item(
    item_id: str,
    body: KnowledgeItemUpdate,
    db: Session = Depends(get_db_session),
):
    updates = {}
    if body.tags is not None:
        updates["tags"] = json.dumps(body.tags)
    if body.title is not None:
        updates["title"] = body.title
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    item = KnowledgeItemRepository.update(db, item_id, updates)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return _serialize(item)


@router.delete("/{item_id}")
def delete_knowledge_item(item_id: str, db: Session = Depends(get_db_session)):
    ok = KnowledgeItemRepository.delete(db, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


def _serialize(item, include_content: bool = False) -> dict:
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
        # YouTube-specific metadata (nullable for non-youtube sources)
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
