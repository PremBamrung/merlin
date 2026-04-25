"""
GET /api/tags  — unique tags with counts across all knowledge items
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.models import KnowledgeItem

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags(db: Session = Depends(get_db_session)):
    rows = db.query(KnowledgeItem.tags).filter(KnowledgeItem.tags.isnot(None)).all()
    counts: dict[str, int] = {}
    for (raw,) in rows:
        try:
            tags = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    counts[tag.strip()] = counts.get(tag.strip(), 0) + 1
    return [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda x: -x[1])]
