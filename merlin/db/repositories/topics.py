"""TopicRepository — CRUD for the topic taxonomy + item↔topic assignments.

All SQL/ORM lives here (the architecture rule keeps queries out of the service
layer). Methods are synchronous and take a Session; the caller commits.
"""

from datetime import UTC, datetime
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from merlin.db.models import ItemTopic, KnowledgeItem, Topic, TopicProposal


def _now() -> datetime:
    return datetime.now(UTC)


class TopicRepository:
    # -- Topic CRUD --------------------------------------------------------

    @staticmethod
    def get(session: Session, topic_id: str) -> Topic | None:
        return session.get(Topic, topic_id)

    @staticmethod
    def get_by_slug(session: Session, slug: str) -> Topic | None:
        return session.query(Topic).filter(Topic.slug == slug).first()

    @staticmethod
    def list_active(session: Session, status: str | None = "active") -> list[Topic]:
        """Topics filtered by status (None = all), ordered by label."""
        q = session.query(Topic)
        if status:
            q = q.filter(Topic.status == status)
        return q.order_by(Topic.label.asc()).all()

    @staticmethod
    def counts_by_topic(session: Session) -> dict[str, int]:
        """topic_id -> number of items assigned it (any primary/secondary)."""
        rows = (
            session.query(ItemTopic.topic_id, func.count(ItemTopic.knowledge_item_id))
            .group_by(ItemTopic.topic_id)
            .all()
        )
        return dict(rows)

    @staticmethod
    def create(
        session: Session,
        label: str,
        slug: str,
        origin: str = "user",
        description: str | None = None,
    ) -> Topic:
        topic = Topic(
            label=label,
            slug=slug,
            status="active",
            origin=origin,
            description=description,
            created_at=_now(),
        )
        session.add(topic)
        session.flush()
        return topic

    @staticmethod
    def update(
        session: Session,
        topic_id: str,
        *,
        label: str | None = None,
        slug: str | None = None,
        status: str | None = None,
        description: str | None = None,
    ) -> Topic | None:
        topic = session.get(Topic, topic_id)
        if not topic:
            return None
        if label is not None:
            topic.label = label
        if slug is not None:
            topic.slug = slug
        if status is not None:
            topic.status = status
        if description is not None:
            topic.description = description
        return topic

    @staticmethod
    def delete(session: Session, topic_id: str) -> bool:
        topic = session.get(Topic, topic_id)
        if not topic:
            return False
        session.delete(topic)  # cascades item_topics via relationship + FK
        return True

    @staticmethod
    def merge(session: Session, src_id: str, dest_id: str) -> bool:
        """Repoint every assignment from src topic onto dest, then delete src.

        Dedups where an item already carries dest. Preserves "at most one
        primary per item": if the src row was the item's primary, dest becomes
        primary (whether dest was already present or the src row is repointed).
        """
        src = session.get(Topic, src_id)
        dest = session.get(Topic, dest_id)
        if not src or not dest or src_id == dest_id:
            return False

        dest_items = {
            it.knowledge_item_id: it
            for it in session.query(ItemTopic).filter(ItemTopic.topic_id == dest_id)
        }
        for row in session.query(ItemTopic).filter(ItemTopic.topic_id == src_id).all():
            dest_row = dest_items.get(row.knowledge_item_id)
            if dest_row is not None:
                # Item already has dest — drop the src row, promote dest if src
                # carried the primary flag.
                if row.is_primary:
                    dest_row.is_primary = True
                session.delete(row)
            else:
                # Repoint the src assignment onto dest (keeps is_primary).
                row.topic_id = dest_id
        session.flush()
        session.delete(src)
        return True

    # -- Assignments (item_topics) ----------------------------------------

    @staticmethod
    def assignments_for_items(
        session: Session, item_ids: list[str]
    ) -> dict[str, list[dict]]:
        """Map item_id -> [{slug, label, is_primary}], primary first.

        Batched (one query) so serializing a page of items is not N+1.
        """
        if not item_ids:
            return {}
        rows = (
            session.query(
                ItemTopic.knowledge_item_id,
                Topic.slug,
                Topic.label,
                ItemTopic.is_primary,
            )
            .join(Topic, Topic.id == ItemTopic.topic_id)
            .filter(ItemTopic.knowledge_item_id.in_(item_ids))
            .all()
        )
        out: dict[str, list[dict]] = {}
        for item_id, slug, label, is_primary in rows:
            out.setdefault(item_id, []).append(
                {"slug": slug, "label": label, "is_primary": bool(is_primary)}
            )
        for lst in out.values():
            lst.sort(key=lambda t: (not t["is_primary"], t["label"].lower()))
        return out

    @staticmethod
    def get_assignments(session: Session, item_id: str) -> list[ItemTopic]:
        return (
            session.query(ItemTopic)
            .filter(ItemTopic.knowledge_item_id == item_id)
            .all()
        )

    @staticmethod
    def has_user_assignment(session: Session, item_id: str) -> bool:
        return (
            session.query(ItemTopic)
            .filter(ItemTopic.knowledge_item_id == item_id)
            .filter(ItemTopic.assigned_by == "user")
            .first()
            is not None
        )

    @staticmethod
    def clear_assignments(
        session: Session, item_id: str, assigned_by: str | None = None
    ) -> None:
        """Delete an item's assignments (optionally only those of one origin)."""
        q = session.query(ItemTopic).filter(ItemTopic.knowledge_item_id == item_id)
        if assigned_by is not None:
            q = q.filter(ItemTopic.assigned_by == assigned_by)
        for row in q.all():
            session.delete(row)
        session.flush()

    @staticmethod
    def add_assignment(
        session: Session,
        item_id: str,
        topic_id: str,
        *,
        is_primary: bool,
        assigned_by: str,
        confidence: float | None = None,
    ) -> ItemTopic:
        row = ItemTopic(
            knowledge_item_id=item_id,
            topic_id=topic_id,
            is_primary=is_primary,
            assigned_by=assigned_by,
            confidence=confidence,
            created_at=_now(),
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def uncategorised_count(session: Session) -> int:
        """Completed items with no item_topics row at all."""
        assigned = select(ItemTopic.knowledge_item_id).where(
            ItemTopic.knowledge_item_id == KnowledgeItem.id
        )
        return (
            session.query(func.count(KnowledgeItem.id))
            .filter(KnowledgeItem.status == "completed")
            .filter(~assigned.exists())
            .scalar()
            or 0
        )

    @staticmethod
    def uncategorised_items(
        session: Session, limit: int | None = None
    ) -> list[KnowledgeItem]:
        """Completed items with no topic assignment (for the proposal pipeline
        and backfill), newest first."""
        assigned = select(ItemTopic.knowledge_item_id).where(
            ItemTopic.knowledge_item_id == KnowledgeItem.id
        )
        q = (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(~assigned.exists())
            .order_by(KnowledgeItem.ingested_at.desc())
        )
        if limit is not None:
            q = q.limit(limit)
        return q.all()

    @staticmethod
    def classifiable_item_ids(session: Session) -> list[str]:
        """Completed items with no user-assigned topic — the full re-scan feeder.

        Covers uncategorised items AND already-LLM-classified ones, so a full
        re-scan can re-decide the whole library against the current taxonomy
        (unlike backfill, which only touches the uncategorised pile). User-pinned
        items are excluded: `classify_and_persist` would discard the result.
        Newest first.
        """
        has_user = select(ItemTopic.knowledge_item_id).where(
            ItemTopic.knowledge_item_id == KnowledgeItem.id,
            ItemTopic.assigned_by == "user",
        )
        q = (
            session.query(KnowledgeItem.id)
            .filter(KnowledgeItem.status == "completed")
            .filter(~has_user.exists())
            .order_by(KnowledgeItem.ingested_at.desc())
        )
        return [r[0] for r in q.all()]

    @staticmethod
    def llm_member_ids(session: Session, topic_id: str) -> list[str]:
        """Completed items where `topic_id` is an LLM-assigned topic (primary or
        secondary) AND the item has no user-assigned topic — the re-scan feeder.

        User-assigned items are excluded: `classify_and_persist` would discard the
        result (§10.4), so re-classifying them just wastes an LLM call. Newest
        first, mirroring `uncategorised_items`.
        """
        # Aliased so this subquery keeps its own item_topics FROM instead of
        # auto-correlating away the outer ItemTopic join.
        user_it = aliased(ItemTopic)
        has_user = select(user_it.knowledge_item_id).where(
            user_it.knowledge_item_id == KnowledgeItem.id,
            user_it.assigned_by == "user",
        )
        q = (
            session.query(KnowledgeItem.id)
            .join(ItemTopic, ItemTopic.knowledge_item_id == KnowledgeItem.id)
            .filter(KnowledgeItem.status == "completed")
            .filter(ItemTopic.topic_id == topic_id)
            .filter(ItemTopic.assigned_by == "llm")
            .filter(~has_user.exists())
            .order_by(KnowledgeItem.ingested_at.desc())
        )
        return [r[0] for r in q.all()]

    @staticmethod
    def member_items(session: Session, ids: list[str]) -> list[dict]:
        """Resolve a proposal's snapshot ids to [{id, title}], dropping any that
        no longer exist (drift) and preserving the snapshot order."""
        if not ids:
            return []
        rows = (
            session.query(KnowledgeItem.id, KnowledgeItem.title)
            .filter(KnowledgeItem.id.in_(ids))
            .all()
        )
        title_by_id = dict(rows)
        return [{"id": i, "title": title_by_id[i]} for i in ids if i in title_by_id]

    # -- Proposals (topic_proposals) --------------------------------------

    @staticmethod
    def create_proposal(
        session: Session,
        proposed_label: str,
        item_ids: list[str],
        rationale: str | None,
        batch_id: str,
    ) -> TopicProposal:
        row = TopicProposal(
            proposed_label=proposed_label,
            item_ids=json.dumps(item_ids),
            rationale=rationale,
            status="pending",
            batch_id=batch_id,
            created_at=_now(),
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def get_proposal(session: Session, proposal_id: str) -> TopicProposal | None:
        return session.get(TopicProposal, proposal_id)

    @staticmethod
    def list_proposals(
        session: Session, batch_id: str | None = None, status: str = "pending"
    ) -> list[TopicProposal]:
        q = session.query(TopicProposal)
        if status:
            q = q.filter(TopicProposal.status == status)
        if batch_id:
            q = q.filter(TopicProposal.batch_id == batch_id)
        return q.order_by(TopicProposal.created_at.desc()).all()

    @staticmethod
    def supersede_pending(session: Session) -> int:
        """Mark all still-pending proposals superseded (a new run replaces them).
        Returns how many were updated."""
        return (
            session.query(TopicProposal)
            .filter(TopicProposal.status == "pending")
            .update({TopicProposal.status: "superseded"}, synchronize_session=False)
        )
