"""
KnowledgeItemRepository — CRUD for knowledge_items + youtube_metadata.
All methods are synchronous; session is passed in (FastAPI Depends pattern).
"""

from datetime import UTC, datetime

from sqlalchemy import text
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
    def get_by_id(session: Session, item_id: str) -> KnowledgeItem | None:
        return session.get(KnowledgeItem, item_id)

    @staticmethod
    def get_by_source(
        session: Session, source_type: str, source_id: str
    ) -> KnowledgeItem | None:
        return (
            session.query(KnowledgeItem)
            .filter_by(source_type=source_type, source_id=source_id)
            .first()
        )

    @staticmethod
    def list_all(
        session: Session,
        source_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
        read: bool | None = None,
        saved: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "newest",
    ) -> tuple[list[KnowledgeItem], int]:
        """Return (items, total_count) with optional filters.

        read/saved: None = no filter; True/False match presence of the
        corresponding timestamp (read_at / saved_at).
        sort: newest | oldest | longest | title
        """
        q = session.query(KnowledgeItem)

        if source_type:
            q = q.filter(KnowledgeItem.source_type == source_type)
        if status:
            q = q.filter(KnowledgeItem.status == status)
        if read is not None:
            q = q.filter(
                KnowledgeItem.read_at.isnot(None)
                if read
                else KnowledgeItem.read_at.is_(None)
            )
        if saved is not None:
            q = q.filter(
                KnowledgeItem.saved_at.isnot(None)
                if saved
                else KnowledgeItem.saved_at.is_(None)
            )
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

        order_by = {
            "newest": KnowledgeItem.ingested_at.desc(),
            "oldest": KnowledgeItem.ingested_at.asc(),
            "longest": KnowledgeItem.word_count.desc().nulls_last(),
            "title": KnowledgeItem.title.asc(),
        }.get(sort, KnowledgeItem.ingested_at.desc())

        total = q.count()
        items = (
            q.order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(
        session: Session, item_id: str, updates: dict
    ) -> KnowledgeItem | None:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        for k, v in updates.items():
            setattr(item, k, v)
        item.updated_at = datetime.now(UTC)
        return item

    @staticmethod
    def delete(session: Session, item_id: str) -> bool:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        session.delete(item)
        return True

    @staticmethod
    def set_read(session: Session, item_id: str, read: bool) -> KnowledgeItem | None:
        """Mark an item read (now) or unread (clear read_at). None if missing.

        Deliberately does NOT bump updated_at — read/save are consumption state,
        not content edits, and must not reorder content-sorted views.
        """
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        item.read_at = datetime.now(UTC) if read else None
        return item

    @staticmethod
    def set_saved(session: Session, item_id: str, saved: bool) -> KnowledgeItem | None:
        """Star (now) or un-star (clear saved_at) an item. None if missing."""
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        item.saved_at = datetime.now(UTC) if saved else None
        return item

    @staticmethod
    def count_unread(session: Session) -> int:
        """Completed items not yet read — the Feed queue size."""
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(KnowledgeItem.read_at.is_(None))
            .count()
        )

    @staticmethod
    def mark_all_read(session: Session) -> int:
        """Bulk-mark every completed, unread item read. Returns the count.

        Clears the Feed queue in one shot (also the one-time backfill so already
        ingested items count as 'already viewed').
        """
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(KnowledgeItem.read_at.is_(None))
            .update({KnowledgeItem.read_at: datetime.now(UTC)}, synchronize_session=False)
        )

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
        item.updated_at = datetime.now(UTC)
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
    def get_by_video_id(session: Session, video_id: str) -> YouTubeMetadata | None:
        return session.query(YouTubeMetadata).filter_by(video_id=video_id).first()
