"""
KnowledgeItemRepository — CRUD for knowledge_items + youtube_metadata.
All methods are synchronous; session is passed in (FastAPI Depends pattern).
"""

from datetime import datetime, timezone
import json
from typing import Any, Optional

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from merlin.db.models import KnowledgeItem, YouTubeMetadata


class KnowledgeItemRepository:
    @staticmethod
    def create(session: Session, data: dict) -> KnowledgeItem:
        """Insert a new KnowledgeItem. Returns the saved instance."""
        item = KnowledgeItem(**data)
        session.add(item)
        session.flush()  # get generated id without committing
        return item

    @staticmethod
    def get_by_id(session: Session, item_id: str) -> Optional[KnowledgeItem]:
        return session.get(KnowledgeItem, item_id)

    @staticmethod
    def get_by_source(
        session: Session, source_type: str, source_id: str
    ) -> Optional[KnowledgeItem]:
        return (
            session.query(KnowledgeItem)
            .filter_by(source_type=source_type, source_id=source_id)
            .first()
        )

    @staticmethod
    def list_all(
        session: Session,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeItem], int]:
        """Return (items, total_count) with optional filters."""
        q = session.query(KnowledgeItem)

        if source_type:
            q = q.filter(KnowledgeItem.source_type == source_type)
        if status:
            q = q.filter(KnowledgeItem.status == status)
        if tags:
            # Each tag must appear somewhere in the JSON tags string
            for tag in tags:
                q = q.filter(KnowledgeItem.tags.contains(tag))
        if search:
            # FTS5 search via subquery
            fts_ids = session.execute(
                text(
                    "SELECT ki.id FROM knowledge_items ki "
                    "JOIN knowledge_fts fts ON ki.rowid = fts.rowid "
                    "WHERE knowledge_fts MATCH :q"
                ),
                {"q": search},
            ).fetchall()
            ids = [row[0] for row in fts_ids]
            if ids:
                q = q.filter(KnowledgeItem.id.in_(ids))
            else:
                return [], 0

        total = q.count()
        items = (
            q.order_by(KnowledgeItem.ingested_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(
        session: Session, item_id: str, updates: dict
    ) -> Optional[KnowledgeItem]:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        for k, v in updates.items():
            setattr(item, k, v)
        item.updated_at = datetime.now(timezone.utc)
        return item

    @staticmethod
    def delete(session: Session, item_id: str) -> bool:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        session.delete(item)
        return True

    @staticmethod
    def clear_summary(session: Session, item_id: str) -> bool:
        """Clear summary fields only, keep raw_content and metadata."""
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        item.summary = None
        item.summary_length = None
        item.llm_model = None
        item.topics = None
        item.status = "pending"
        item.error_message = None
        item.updated_at = datetime.now(timezone.utc)
        return True


class YouTubeMetadataRepository:
    @staticmethod
    def upsert(session: Session, knowledge_item_id: str, data: dict) -> YouTubeMetadata:
        existing = session.get(YouTubeMetadata, knowledge_item_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        meta = YouTubeMetadata(knowledge_item_id=knowledge_item_id, **data)
        session.add(meta)
        session.flush()
        return meta

    @staticmethod
    def get_by_video_id(session: Session, video_id: str) -> Optional[YouTubeMetadata]:
        return session.query(YouTubeMetadata).filter_by(video_id=video_id).first()
