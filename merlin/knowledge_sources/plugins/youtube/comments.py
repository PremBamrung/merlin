"""Top YouTube comments via yt-dlp — no API key, same cookies as the audio path.

YouTube's "Top comments" order is its own relevance ranking (a 2k-like comment
can sit above a 500k one), so the fetched page is re-sorted: pinned first, then
by likes. Top-level comments only — replies are skipped.

Comments come from the watch page, not the transcript endpoint, so they have
their own spacing (YOUTUBE_COMMENTS_MIN_INTERVAL between fetches, across all
workers, plus a short sleep between the calls inside one fetch) rather than
queueing behind subtitle fetches — but they share the subtitle limiter's
IP-block cooldown: nothing is fetched while YouTube is blocking us, and a block
seen here trips it for the subtitle path too.
"""

from datetime import UTC, datetime
from pathlib import Path
import tempfile

import yt_dlp

from merlin.config import settings
from merlin.core.logging import logger
from merlin.core.rate_limit import MinIntervalRateLimiter
from merlin.knowledge_sources.plugins.youtube.cookies import ytdlp_cookie_copy
from merlin.knowledge_sources.plugins.youtube.extractors import (
    _cooldown_skip_message,
    _is_ip_block,
    _subtitle_rate_limiter,
)

# Spaces comment fetches across ingest workers / Reader refreshes.
_comments_rate_limiter = MinIntervalRateLimiter(
    settings.youtube_comments_min_interval, name="youtube-comments"
)
# yt-dlp's own pause between the HTTP calls of one fetch (watch page, player,
# comment pages), so a single fetch isn't a burst either.
_SLEEP_BETWEEN_REQUESTS = 1.0


class CommentsUnavailable(Exception):
    """Comments couldn't be fetched (disabled, IP-block cooldown, or an error)."""


def _normalize(raw: dict) -> dict | None:
    text = (raw.get("text") or "").strip()
    if not text:
        return None
    ts = raw.get("timestamp")
    return {
        "comment_id": raw.get("id"),
        "author": raw.get("author"),
        "text": text,
        "like_count": raw.get("like_count") or 0,
        "is_pinned": bool(raw.get("is_pinned")),
        "is_uploader": bool(raw.get("author_is_uploader")),
        # yt-dlp derives this from "2 years ago" — approximate by design.
        "posted_at": datetime.fromtimestamp(ts, UTC) if ts else None,
    }


def fetch_top_comments(video_id: str, limit: int | None = None) -> list[dict]:
    """The video's top-level comments, pinned first then most-liked.

    Raises CommentsUnavailable when fetching is disabled
    (YOUTUBE_COMMENTS_LIMIT=0), cooled down after an IP block, or fails.
    An empty list means the video genuinely has no comments (or they're off).
    """
    limit = settings.youtube_comments_limit if limit is None else limit
    if limit <= 0:
        raise CommentsUnavailable("Comment fetching is off (YOUTUBE_COMMENTS_LIMIT=0)")
    if _subtitle_rate_limiter.in_cooldown():
        raise CommentsUnavailable(_cooldown_skip_message())
    _comments_rate_limiter.wait()
    # Another worker may have hit a block while we waited for our slot.
    if _subtitle_rate_limiter.in_cooldown():
        raise CommentsUnavailable(_cooldown_skip_message())

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory(prefix="merlin_comments_") as tmp:
        opts = {
            "skip_download": True,
            "getcomments": True,
            "quiet": True,
            "noprogress": True,
            "sleep_interval_requests": _SLEEP_BETWEEN_REQUESTS,
            "extractor_args": {
                "youtube": {
                    "comment_sort": ["top"],
                    # max-comments, max-parents, max-replies → top-level only
                    "max_comments": [str(limit), str(limit), "0"],
                }
            },
        }
        cookie_copy = ytdlp_cookie_copy(tmp)
        if cookie_copy:
            opts["cookiefile"] = cookie_copy
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False) or {}
        except Exception as e:
            if _is_ip_block(str(e)):
                cooldown = _subtitle_rate_limiter.trip_cooldown()
                logger.warning(
                    f"YouTube blocked the comments fetch for {video_id}; pausing "
                    f"YouTube requests for {cooldown / 60:.0f} min"
                )
            raise CommentsUnavailable(f"Couldn't fetch comments: {e}") from e
        finally:
            if cookie_copy:
                Path(cookie_copy).unlink(missing_ok=True)

    comments = [
        c
        for raw in info.get("comments") or []
        if raw.get("parent", "root") == "root" and (c := _normalize(raw))
    ]
    comments.sort(key=lambda c: (not c["is_pinned"], -c["like_count"]))
    logger.info(f"Fetched {len(comments[:limit])} top comments for {video_id}")
    return comments[:limit]


def try_fetch_top_comments(video_id: str) -> list[dict] | None:
    """Best-effort `fetch_top_comments` for the ingest path: None when nothing
    was fetched (off / cooled down / failed), so the caller can tell "not
    fetched" from "fetched, none" and a comment failure never fails an ingest."""
    try:
        return fetch_top_comments(video_id)
    except CommentsUnavailable as e:
        logger.warning(f"Skipping comments for {video_id}: {e}")
        return None
