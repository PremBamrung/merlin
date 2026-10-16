"""Top YouTube comments — read the stored set, or re-fetch it on demand.

Comments are fetched best-effort at ingest (and self-healed for older items on
re-summarise — see `services.ingest`). This module serves the Reader's
Comments tab and the chat tools: `list_comments` reads what's stored,
`refresh_comments` replaces it with a fresh fetch (synchronous — a top-level
page is one ~3-5 s yt-dlp call, not worth a background task).
"""

from datetime import UTC

from merlin.config import settings
from merlin.db.engine import SessionFactory
from merlin.db.repositories.knowledge import (
    KnowledgeItemRepository,
    YouTubeCommentRepository,
)
from merlin.knowledge_sources.plugins.youtube.comments import (
    CommentsUnavailable,
    fetch_top_comments,
)


def comment_dict(c) -> dict:
    """A stored comment row as a plain dict (the shape the fetcher returns)."""
    return {
        "comment_id": c.comment_id,
        "author": c.author,
        "text": c.text,
        "like_count": c.like_count or 0,
        "is_pinned": bool(c.is_pinned),
        "is_uploader": bool(c.is_uploader),
        "posted_at": c.posted_at,
    }


def _iso(dt) -> str | None:
    """ISO string with an explicit UTC offset — SQLite hands back naive
    datetimes, which the browser would otherwise read as local time."""
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).isoformat()


def _serialize(c) -> dict:
    d = comment_dict(c)
    d["posted_at"] = _iso(c.posted_at)
    return d


def list_comments(item_id: str, limit: int | None = None) -> dict | None:
    """The item's stored top comments, best first; None if the item is missing.

    `fetched_at` is null when they were never fetched; `enabled` is False when
    YOUTUBE_COMMENTS_LIMIT=0 (so the UI can say why there are none).
    """
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if item is None:
            return None
        meta = item.youtube_metadata
        fetched = meta.comments_fetched_at if meta else None
        rows = YouTubeCommentRepository.list_for_item(session, item_id)
        if limit is not None:
            rows = rows[: max(limit, 0)]
        return {
            "item_id": item.id,
            "title": item.title,
            "source_type": item.source_type,
            "enabled": settings.youtube_comments_limit > 0,
            "fetched_at": _iso(fetched),
            "comments": [_serialize(c) for c in rows],
        }


def refresh_comments(item_id: str) -> dict | None:
    """Re-fetch the item's top comments from YouTube and replace the stored set.

    Returns the new `list_comments` payload; None if the item is missing.
    Raises ValueError for a non-YouTube item, or when the fetch is off, paused
    by an IP-block cooldown, or fails — the stored set is then left untouched.
    """
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if item is None:
            return None
        if item.source_type != "youtube" or item.youtube_metadata is None:
            raise ValueError("Comments are only available for YouTube videos.")
        video_id = item.youtube_metadata.video_id

    try:
        fetched = fetch_top_comments(video_id)
    except CommentsUnavailable as e:
        raise ValueError(str(e)) from e

    with SessionFactory() as session:
        YouTubeCommentRepository.replace(session, item_id, fetched)
        session.commit()
    return list_comments(item_id)
