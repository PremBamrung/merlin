"""
DigestActionRepository — review decisions over the Inbox queue.

A `digest_actions` row records that an item has been triaged (kept or
dismissed). One action per item: recording a new decision replaces the old one.
Acting on an item is what removes it from the pending Inbox queue.
"""

from sqlalchemy.orm import Session

from merlin.db.models import DigestAction, KnowledgeItem


class DigestActionRepository:
    @staticmethod
    def list_pending(session: Session, limit: int = 50) -> list[KnowledgeItem]:
        """Recent completed items that have not yet been triaged, newest first."""
        acted = session.query(DigestAction.knowledge_item_id)
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(~KnowledgeItem.id.in_(acted))
            .order_by(KnowledgeItem.ingested_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_pending(session: Session) -> int:
        acted = session.query(DigestAction.knowledge_item_id)
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(~KnowledgeItem.id.in_(acted))
            .count()
        )

    @staticmethod
    def record(session: Session, item_id: str, action: str) -> DigestAction:
        """Record (replacing any prior) the review decision for an item."""
        session.query(DigestAction).filter(
            DigestAction.knowledge_item_id == item_id
        ).delete(synchronize_session=False)
        da = DigestAction(knowledge_item_id=item_id, action=action)
        session.add(da)
        return da

    @staticmethod
    def count(session: Session) -> int:
        return session.query(DigestAction).count()
