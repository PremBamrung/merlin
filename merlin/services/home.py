"""The chat-first home's "since last time" digest (docs/WEB_PORT_PLAN.md
Batch E): what arrived since the client's last visit, what's still waiting,
the conversation to pick up, and the topic that moved most.

`since` is held by the client (its last visit); there is no server-side
marker. "New" means ingested at or after it — a re-summarise bumps
`ingested_at` too, which is acceptable for a nudge.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func

from merlin.db.engine import SessionFactory
from merlin.db.models import ItemTopic, KnowledgeItem, Topic
from merlin.services import chat_history
from merlin.services.library import serialize_item

STRIP_SIZE = 5
_SNIPPET = 160


def _naive_utc(dt: datetime) -> datetime:
    """Stored timestamps are naive UTC; compare like with like."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _last_reply(thread_id: str) -> tuple[str | None, int]:
    """The tail of the thread's last answer, and how many sources it cited."""
    thread = chat_history.get_thread(thread_id)
    if not thread:
        return None, 0
    for message in reversed(thread["messages"]):
        if message["role"] != "assistant":
            continue
        parts = [p for p in message["parts"] if isinstance(p, dict)]
        text = " ".join(
            (p.get("text") or "") for p in parts if p.get("type") == "text"
        ).strip()
        sources = sum(
            len((p.get("data") or {}).get("items") or [])
            for p in parts
            if p.get("type") == "data-citations"
        )
        if text:
            flat = " ".join(text.split())
            tail = flat if len(flat) <= _SNIPPET else "…" + flat[-_SNIPPET:]
            return tail, sources
    return None, 0


def digest(since: datetime) -> dict:
    """Everything the home's "since last time" line, Continue card, new-items
    strip and suggestions need, in one call."""
    since = _naive_utc(since)
    with SessionFactory() as session:
        completed = session.query(KnowledgeItem).filter(
            KnowledgeItem.status == "completed"
        )
        unread_q = completed.filter(KnowledgeItem.read_at.is_(None))
        new_q = completed.filter(KnowledgeItem.ingested_at >= since)

        unread_count = unread_q.count()
        new_since_count = new_q.count()

        # The strip shows what's new since the last visit; when nothing is, it
        # shows what's still unread, so home is never an empty shelf.
        strip_q = (new_q if new_since_count else unread_q).order_by(
            KnowledgeItem.ingested_at.desc()
        )
        strip = [serialize_item(i, topics=[]) for i in strip_q.limit(STRIP_SIZE)]

        def busiest(base) -> tuple[str, str, int] | None:
            row = (
                base.join(ItemTopic, ItemTopic.knowledge_item_id == KnowledgeItem.id)
                .join(Topic, Topic.id == ItemTopic.topic_id)
                .filter(ItemTopic.is_primary.is_(True), Topic.status == "active")
                .with_entities(Topic.slug, Topic.label, func.count(KnowledgeItem.id))
                .group_by(Topic.id)
                .order_by(func.count(KnowledgeItem.id).desc(), Topic.label)
                .first()
            )
            return (row[0], row[1], row[2]) if row else None

        busy = busiest(new_q) if new_since_count else None
        busy_kind = "new"
        if busy is None:
            busy, busy_kind = busiest(unread_q), "unread"

        saved = (
            completed.filter(KnowledgeItem.saved_at.isnot(None))
            .order_by(KnowledgeItem.saved_at.desc())
            .first()
        )
        saved_revisit = serialize_item(saved, topics=[]) if saved else None

    threads = chat_history.list_threads()
    continue_thread = None
    if threads:
        t = threads[0]
        reply, sources = _last_reply(t["id"])
        continue_thread = {**t, "last_reply": reply, "source_count": sources}

    return {
        "since": since.replace(tzinfo=UTC).isoformat(),
        "unread_count": unread_count,
        "new_since_count": new_since_count,
        "strip": strip,
        "strip_kind": "new" if new_since_count else "unread",
        "continue_thread": continue_thread,
        "busy_topic": (
            {"slug": busy[0], "label": busy[1], "count": busy[2], "kind": busy_kind}
            if busy
            else None
        ),
        "saved_revisit": saved_revisit,
    }
