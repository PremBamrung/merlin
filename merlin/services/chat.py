"""Chat service — the application-layer facade for agentic chat.

The library-wide chat is a **Pydantic AI agent** (tool-calling: it searches and
reads the knowledge base itself); the Reader's single-item chat reuses a
tool-less agent whose context is the item's full transcript, supplied as per-run
instructions. Both run on the same OpenRouter chat model and are streamed to the
browser through `api`'s `VercelAIAdapter` glue — this module exposes the pieces
the route needs without `api` reaching into `merlin.rag` directly (preserving
the `api → services → rag` dependency arrow).
"""

from __future__ import annotations

from merlin.rag.agent import ChatDeps, agent, item_agent
from merlin.rag.model import build_chat_model
from merlin.rag.prompts import ITEM_CHAT_SYSTEM_PROMPT, format_item_context
from merlin.services import library

__all__ = [
    "ChatDeps",
    "agent",
    "item_agent",
    "build_chat_model",
    "deps_from_filters",
    "item_instructions",
]


def deps_from_filters(filters: dict | None) -> ChatDeps:
    """Build the per-run dependencies from the chat's FilterBar selections."""
    filters = filters or {}
    return ChatDeps(
        source_types=filters.get("source_types") or None,
        tags=filters.get("tags") or None,
    )


def item_instructions(item_id: str) -> str:
    """Per-run instructions for single-item (Reader) chat.

    Stuffs the item's metadata + summary + full transcript into the system
    instructions, exactly as the previous sync path did. Raises ValueError if
    the item doesn't exist (the route maps this to a 400).
    """
    item = library.get_item(item_id)
    if item is None:
        raise ValueError("Item not found.")
    return ITEM_CHAT_SYSTEM_PROMPT.format(context=format_item_context(item))
