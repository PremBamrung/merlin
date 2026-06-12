"""
Library service — read/update/delete knowledge items and list tags.

Returns plain dicts (not ORM objects), so the UI never touches a live session
or a detached instance. Serialization is done while the session is open.
"""

import json

from merlin.db.engine import SessionFactory
from merlin.db.repositories.knowledge import KnowledgeItemRepository


def serialize_item(item, include_content: bool = False) -> dict:
    """Flatten a KnowledgeItem (+ youtube_metadata) into a plain dict.

    Must be called while the owning session is open (touches the
    youtube_metadata relationship).
    """
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
        # YouTube-specific (nullable for non-youtube sources)
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


def list_items(
    source_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    tags: list[str] | None = None,
    page: int = 1,
    per_page: int = 20,
    sort: str = "newest",
) -> dict:
    with SessionFactory() as session:
        items, total = KnowledgeItemRepository.list_all(
            session,
            source_type=source_type,
            status=status,
            search=search,
            tags=tags,
            page=page,
            page_size=per_page,
            sort=sort,
        )
        return {
            "items": [serialize_item(i) for i in items],
            "total": total,
            "page": page,
            "per_page": per_page,
        }


def get_item(item_id: str) -> dict | None:
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        return serialize_item(item, include_content=True) if item else None


def update_item(
    item_id: str,
    tags: list[str] | None = None,
    title: str | None = None,
) -> dict | None:
    updates = {}
    if tags is not None:
        updates["tags"] = json.dumps(tags)
    if title is not None:
        updates["title"] = title
    if not updates:
        return get_item(item_id)
    with SessionFactory() as session:
        item = KnowledgeItemRepository.update(session, item_id, updates)
        if not item:
            return None
        result = serialize_item(item)
        session.commit()
        return result


def delete_item(item_id: str) -> bool:
    with SessionFactory() as session:
        ok = KnowledgeItemRepository.delete(session, item_id)
        if ok:
            session.commit()
        return ok


def clear_summary(item_id: str) -> bool:
    with SessionFactory() as session:
        ok = KnowledgeItemRepository.clear_summary(session, item_id)
        if ok:
            session.commit()
        return ok


def ingest_timeline() -> list[dict]:
    """Count of items per ingested calendar day, oldest first."""
    from sqlalchemy import func

    from merlin.db.models import KnowledgeItem

    with SessionFactory() as session:
        day = func.date(KnowledgeItem.ingested_at)
        rows = (
            session.query(day, func.count(KnowledgeItem.id))
            .filter(KnowledgeItem.ingested_at.isnot(None))
            .group_by(day)
            .order_by(day)
            .all()
        )
    return [{"date": d, "count": c} for d, c in rows if d]


def top_channels(limit: int = 12) -> list[dict]:
    """Most frequent YouTube channels (falls back to author), by item count."""
    from sqlalchemy import func

    from merlin.db.models import KnowledgeItem, YouTubeMetadata

    with SessionFactory() as session:
        rows = (
            session.query(YouTubeMetadata.channel, func.count(KnowledgeItem.id))
            .join(KnowledgeItem, KnowledgeItem.id == YouTubeMetadata.knowledge_item_id)
            .filter(YouTubeMetadata.channel.isnot(None))
            .group_by(YouTubeMetadata.channel)
            .order_by(func.count(KnowledgeItem.id).desc())
            .limit(limit)
            .all()
        )
    return [{"name": name, "count": count} for name, count in rows if name]


def count_channels() -> int:
    """Number of distinct YouTube channels."""
    from sqlalchemy import distinct, func

    from merlin.db.models import YouTubeMetadata

    with SessionFactory() as session:
        return (
            session.query(func.count(distinct(YouTubeMetadata.channel)))
            .filter(YouTubeMetadata.channel.isnot(None))
            .scalar()
            or 0
        )


def status_counts() -> list[dict]:
    """Item count per status."""
    from sqlalchemy import func

    from merlin.db.models import KnowledgeItem

    with SessionFactory() as session:
        rows = (
            session.query(KnowledgeItem.status, func.count(KnowledgeItem.id))
            .group_by(KnowledgeItem.status)
            .all()
        )
    return [{"name": name or "unknown", "count": count} for name, count in rows]


def list_source_types() -> list[dict]:
    """Distinct source types with item counts, most frequent first."""
    from sqlalchemy import func

    from merlin.db.models import KnowledgeItem

    with SessionFactory() as session:
        rows = (
            session.query(KnowledgeItem.source_type, func.count(KnowledgeItem.id))
            .group_by(KnowledgeItem.source_type)
            .all()
        )
    return [
        {"name": name, "count": count}
        for name, count in sorted(rows, key=lambda r: -r[1])
        if name
    ]


def list_tags() -> list[dict]:
    """Unique tags with counts across all items, most frequent first."""
    from merlin.db.models import KnowledgeItem

    with SessionFactory() as session:
        rows = (
            session.query(KnowledgeItem.tags)
            .filter(KnowledgeItem.tags.isnot(None))
            .all()
        )
    counts: dict[str, int] = {}
    for (raw,) in rows:
        tags = _parse_json(raw, None)
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    counts[tag.strip()] = counts.get(tag.strip(), 0) + 1
    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda x: -x[1])
    ]


def _parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return default
