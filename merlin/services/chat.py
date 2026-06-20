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

from collections.abc import Iterator

from merlin.config import settings
from merlin.db.engine import get_db
from merlin.rag.agent import ChatDeps, agent, item_agent
from merlin.rag.model import build_chat_model
from merlin.rag.prompts import (
    ITEM_CHAT_SYSTEM_PROMPT,
    MERLIN_SYSTEM_PROMPT,
    format_context,
    format_item_context,
)
from merlin.rag.retriever import HybridRetriever, RetrievedChunk
from merlin.services import library

_retriever = HybridRetriever()

__all__ = [
    "ChatDeps",
    "agent",
    "item_agent",
    "build_chat_model",
    "deps_from_filters",
    "item_instructions",
    "answer",
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


# --------------------------------------------------------------------------- #
# Sync one-shot RAG — used ONLY by the archived Streamlit "engine room"
# (`streamlit/ui/views/chat.py`), which streams the generator with
# `st.write_stream`. The React daily-driver uses the agentic path above. Kept
# here so the archived surface keeps working; it now benefits from the improved
# retriever too.
# --------------------------------------------------------------------------- #


def answer(
    question: str,
    history: list[dict] | None = None,
    filters: dict | None = None,
) -> tuple[Iterator[str], list[RetrievedChunk]]:
    """Return (token_generator, citations) for the sync Streamlit chat.

    When `filters["item_id"]` is set, chats with that single item using its full
    transcript (no retrieval) and returns no citations. Raises ValueError if the
    item doesn't exist.
    """
    history = history or []
    filters = filters or {}

    item_id = filters.get("item_id")
    if item_id:
        item = library.get_item(item_id)
        if item is None:
            raise ValueError("Item not found.")
        system_content = ITEM_CHAT_SYSTEM_PROMPT.format(
            context=format_item_context(item)
        )
        chunks: list[RetrievedChunk] = []
    else:
        with get_db() as db:
            chunks = _retriever.retrieve(
                db,
                query=question,
                source_types=filters.get("source_types"),
                tag_filters=filters.get("tags"),
                top_k=5,
            )
        system_content = MERLIN_SYSTEM_PROMPT.format(context=format_context(chunks))

    messages = [
        {"role": "system", "content": system_content},
        *history,
        {"role": "user", "content": question},
    ]

    def token_stream() -> Iterator[str]:
        for chunk in settings.llm.stream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                yield content

    return token_stream(), chunks
