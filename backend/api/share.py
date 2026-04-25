"""
POST /api/share         — create a public share token for a knowledge item
GET  /api/share/{token} — retrieve publicly shared knowledge item

Tokens are stored in-memory (reset on restart). Persist to DB in a future migration.
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.repositories.knowledge import KnowledgeItemRepository

router = APIRouter(prefix="/share", tags=["share"])

# In-memory token store: token → knowledge_item_id
_tokens: dict[str, str] = {}


class ShareRequest(BaseModel):
    knowledge_item_id: str


def _parse_json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return default


@router.post("")
def create_share(body: ShareRequest, db: Session = Depends(get_db_session)):
    item = KnowledgeItemRepository.get_by_id(db, body.knowledge_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    token = str(uuid.uuid4())[:8]
    _tokens[token] = body.knowledge_item_id
    return {"token": token, "url": f"/share/{token}"}


@router.get("/{token}")
def get_shared_item(token: str, db: Session = Depends(get_db_session)):
    item_id = _tokens.get(token)
    if not item_id:
        raise HTTPException(status_code=404, detail="Share link not found or expired")
    item = KnowledgeItemRepository.get_by_id(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {
        "id": item.id,
        "source_type": item.source_type,
        "title": item.title,
        "author": item.author,
        "summary": item.summary,
        "tags": _parse_json(item.tags, []),
        "ingested_at": item.ingested_at.isoformat() if item.ingested_at else None,
    }
