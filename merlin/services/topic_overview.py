"""Topic overview + detail for the Topics place (docs/WEB_PORT_PLAN.md Batch G).

The cards need, per topic: its size, what's new and unread since the client's
last visit, three thumbnails and its top tags; the topic page adds hours of
video, channels and sub-tags. One pass over the assignments, aggregated in
Python — the taxonomy is small (~10–30 topics) and so is the library.

"An item is in a topic" means any assignment, primary or secondary — the same
rule the Library's topic filter and the topic counts use.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
import json

from merlin.db.engine import SessionFactory
from merlin.db.models import ItemTopic, KnowledgeItem, Topic, YouTubeMetadata
from merlin.services.library import serialize_item

PREVIEW = 3
TOP_TAGS = 3


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


def _tags(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [t for t in value if isinstance(t, str)] if isinstance(value, list) else []


def _seconds(duration) -> int:
    """'HH:MM:SS' / 'MM:SS' / seconds → seconds (0 when unknown)."""
    if duration is None:
        return 0
    if isinstance(duration, int | float):
        return int(duration)
    total = 0
    for part in str(duration).split(":"):
        if not part.strip().isdigit():
            return 0
        total = total * 60 + int(part)
    return total


def _rows(session, topic_id: str | None = None):
    """(topic_id, item) for every completed item with a topic, newest first."""
    q = (
        session.query(ItemTopic.topic_id, KnowledgeItem)
        .join(KnowledgeItem, KnowledgeItem.id == ItemTopic.knowledge_item_id)
        .filter(KnowledgeItem.status == "completed")
    )
    if topic_id:
        q = q.filter(ItemTopic.topic_id == topic_id)
    return q.order_by(KnowledgeItem.ingested_at.desc()).all()


def overview(since: datetime) -> dict:
    """``{"total", "topics": [...]}`` — active topics, biggest first."""
    since = _naive_utc(since)
    with SessionFactory() as session:
        topics = session.query(Topic).filter(Topic.status == "active").all()
        total = (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .count()
        )
        count: Counter[str] = Counter()
        new: Counter[str] = Counter()
        tags: dict[str, Counter[str]] = defaultdict(Counter)
        preview: dict[str, list] = defaultdict(list)
        for topic_id, item in _rows(session):
            count[topic_id] += 1
            if item.read_at is None and item.ingested_at and item.ingested_at >= since:
                new[topic_id] += 1
            tags[topic_id].update(_tags(item.tags))
            if len(preview[topic_id]) < PREVIEW:
                preview[topic_id].append(item)
        out = [
            {
                "id": t.id,
                "slug": t.slug,
                "label": t.label,
                "status": t.status,
                "origin": t.origin,
                "description": t.description,
                "count": count[t.id],
                "new_count": new[t.id],
                "share": round(count[t.id] / total, 4) if total else 0.0,
                "top_tags": [name for name, _ in tags[t.id].most_common(TOP_TAGS)],
                "preview": [serialize_item(i, topics=[]) for i in preview[t.id]],
            }
            for t in topics
        ]
    out.sort(key=lambda t: (-t["count"], t["label"].lower()))
    return {"total": total, "topics": out}


def detail(slug: str, since: datetime) -> dict | None:
    """One topic's page header: size, share, hours, channels, new, sub-tags."""
    since = _naive_utc(since)
    with SessionFactory() as session:
        topic = session.query(Topic).filter(Topic.slug == slug).first()
        if topic is None:
            return None
        total = (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .count()
        )
        items = [item for _, item in _rows(session, topic.id)]
        ids = [i.id for i in items]
        meta = (
            dict(
                session.query(YouTubeMetadata.knowledge_item_id, YouTubeMetadata)
                .filter(YouTubeMetadata.knowledge_item_id.in_(ids))
                .all()
            )
            if ids
            else {}
        )
        tags: Counter[str] = Counter()
        channels: Counter[str] = Counter()
        seconds = 0
        new_count = 0
        for item in items:
            tags.update(_tags(item.tags))
            m = meta.get(item.id)
            channel = (m.channel if m else None) or item.author
            if channel:
                channels[channel] += 1
            seconds += _seconds(m.duration if m else None)
            if item.read_at is None and item.ingested_at and item.ingested_at >= since:
                new_count += 1
        return {
            "id": topic.id,
            "slug": topic.slug,
            "label": topic.label,
            "status": topic.status,
            "origin": topic.origin,
            "description": topic.description,
            "count": len(items),
            "share": round(len(items) / total, 4) if total else 0.0,
            "seconds": seconds,
            "channel_count": len(channels),
            "new_count": new_count,
            "tags": [{"name": n, "count": c} for n, c in tags.most_common(12)],
            "channels": [{"name": n, "count": c} for n, c in channels.most_common(8)],
        }
