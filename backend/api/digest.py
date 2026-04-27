"""
GET  /api/digest/today       — ranked knowledge items as digest
POST /api/digest/{id}/ingest — mark digest item as ingested (no-op placeholder)
POST /api/digest/{id}/skip   — mark digest item as skipped (no-op placeholder)
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.models import KnowledgeItem

router = APIRouter(prefix="/digest", tags=["digest"])


def _parse_json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return default


def _serialize_item(item: KnowledgeItem) -> dict:
    return {
        "id": item.id,
        "source_type": item.source_type,
        "title": item.title,
        "author": item.author,
        "ingested_at": item.ingested_at.isoformat() if item.ingested_at else None,
        "summary": item.summary,
        "tags": _parse_json(item.tags, []),
        "match_score": 1.0,  # placeholder until embeddings-based scoring is implemented
        "why": f"Recently added · {item.source_type}",
    }


@router.get("/today")
def get_today_digest(limit: int = 20, db: Session = Depends(get_db_session)):
    items = (
        db.query(KnowledgeItem)
        .filter(KnowledgeItem.status == "completed")
        .order_by(KnowledgeItem.ingested_at.desc())
        .limit(limit)
        .all()
    )

    by_type: dict[str, list] = {}
    for item in items:
        key = item.source_type
        by_type.setdefault(key, []).append(_serialize_item(item))

    sections = []
    label_map = {"youtube": "YouTube", "article": "Articles", "pdf": "Documents"}
    for source_type, type_items in by_type.items():
        sections.append(
            {
                "title": f"Recently added · {label_map.get(source_type, source_type)}",
                "subtitle": f"{len(type_items)} item{'s' if len(type_items) != 1 else ''}",
                "items": type_items,
            }
        )

    return {
        "date": None,
        "total": len(items),
        "sections": sections,
    }


@router.post("/{item_id}/ingest")
def ingest_digest_item(item_id: str):
    return {"ok": True, "item_id": item_id}


@router.post("/{item_id}/skip")
def skip_digest_item(item_id: str):
    return {"ok": True, "item_id": item_id}
