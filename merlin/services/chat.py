"""Chat service — the application-layer facade for agentic chat.

The library-wide chat is a **Pydantic AI agent** (tool-calling: it searches and
reads the knowledge base itself); the Reader's single-item chat reuses a
tool-less agent whose context is the item's full transcript, supplied as per-run
instructions. Both run on the same chat model and are streamed to the
browser through `api`'s `VercelAIAdapter` glue — this module exposes the pieces
the route needs without `api` reaching into `merlin.rag` directly (preserving
the `api → services → rag` dependency arrow).
"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from merlin.rag.agent import ChatDeps, agent, item_agent
from merlin.rag.model import (
    build_chat_model,
    thinking_model_settings,
    thinking_supported,
)
from merlin.rag.prompts import ITEM_CHAT_SYSTEM_PROMPT, format_item_context
from merlin.services import comments, library

# The browser's per-message timestamp part (web/src/hooks/useAgentChat.ts).
MESSAGE_TIME_PART = "data-message-time"

__all__ = [
    "ChatDeps",
    "agent",
    "item_agent",
    "build_chat_model",
    "deps_from_filters",
    "deps_from_request",
    "item_instructions",
    "model_settings_from_filters",
    "thinking_supported",
]


def deps_from_filters(filters: dict | None) -> ChatDeps:
    """Build the per-run dependencies from the chat's FilterBar selections."""
    filters = filters or {}
    return ChatDeps(
        source_types=filters.get("source_types") or None,
        tags=filters.get("tags") or None,
    )


def deps_from_request(body: dict | None) -> ChatDeps:
    """Per-run dependencies from the whole chat request body: the FilterBar
    selections plus the user's timezone (`tz`, IANA) and the send time of each
    user message, so the agent knows when every message was written."""
    body = body or {}
    deps = deps_from_filters(body.get("filters"))
    deps.tz = _parse_tz(body.get("tz"))
    deps.user_times = user_message_times(body.get("messages"), body.get("sent_at"))
    return deps


def user_message_times(
    messages: list | None, sent_at: float | int | None
) -> list[datetime | None]:
    """The send time of each user message, oldest first.

    A message's own `data-message-time` part wins (the browser stamps it at the
    end of the turn and saves it with the thread). The latest message has no
    stamp yet, so it takes the request's `sent_at` — the very time the browser
    stamps it with later, so the model sees the same text on every later turn
    and the prompt cache holds. Falls back to the server clock; None where an
    older message was never stamped (threads from before stamping).
    """
    users = [
        m for m in messages or [] if isinstance(m, dict) and m.get("role") == "user"
    ]
    times: list[datetime | None] = []
    for i, msg in enumerate(users):
        ms = next(
            (
                (p.get("data") or {}).get("ms")
                for p in msg.get("parts") or []
                if isinstance(p, dict) and p.get("type") == MESSAGE_TIME_PART
            ),
            None,
        )
        if ms is None and i == len(users) - 1:
            ms = sent_at
        times.append(_from_epoch_ms(ms))
    if users and times[-1] is None:
        times[-1] = datetime.now(UTC)
    return times


def _from_epoch_ms(ms: object) -> datetime | None:
    if isinstance(ms, bool) or not isinstance(ms, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_tz(name: object) -> tzinfo | None:
    """An IANA zone from the browser; None (→ the server's zone) when absent or
    unknown."""
    if not isinstance(name, str) or not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def model_settings_from_filters(filters: dict | None) -> dict | None:
    """Per-request model settings for the chat's `filters.thinking` level
    (minimal|low|medium|high). None — the model's default — when the level is
    missing/invalid or the provider has no thinking control."""
    return thinking_model_settings((filters or {}).get("thinking"))


def item_instructions(item_id: str) -> str:
    """Per-run instructions for single-item (Reader) chat.

    Stuffs the item's metadata + summary + top comments + full transcript into
    the system instructions. Raises ValueError if the item doesn't exist (the
    route maps this to a 400).
    """
    item = library.get_item(item_id)
    if item is None:
        raise ValueError("Item not found.")
    stored = comments.list_comments(item_id)
    item["top_comments"] = stored["comments"] if stored else []
    return ITEM_CHAT_SYSTEM_PROMPT.format(context=format_item_context(item))
