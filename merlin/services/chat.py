"""
Chat service — RAG over the knowledge base.

`answer()` retrieves relevant chunks via FTS5, builds the prompt, and returns a
(token_generator, citations) pair. The UI streams the generator with
`st.write_stream` and renders the citations afterwards — no SSE, no HTTP.
"""

from collections.abc import Iterator

from merlin.config import settings
from merlin.db.engine import get_db
from merlin.rag.prompts import (
    ITEM_CHAT_SYSTEM_PROMPT,
    MERLIN_SYSTEM_PROMPT,
    format_context,
    format_item_context,
)
from merlin.rag.retriever import HybridRetriever, RetrievedChunk
from merlin.services import library

_retriever = HybridRetriever()


def answer(
    question: str,
    history: list[dict] | None = None,
    filters: dict | None = None,
) -> tuple[Iterator[str], list[RetrievedChunk]]:
    """Return (token_generator, citations).

    history: prior turns as [{"role": "user"|"assistant", "content": str}, ...]
    filters: optional {"source_types": [...], "tags": [...], "item_id": str}

    When `item_id` is set, this chats with that single item using its full
    transcript (no FTS retrieval) and returns no citations — the caller is
    already looking at the item. Raises ValueError if the item doesn't exist.
    """
    history = history or []
    filters = filters or {}

    item_id = filters.get("item_id")
    if item_id:
        system_content, chunks = _single_item_context(item_id)
    else:
        chunks = _retrieve(question, filters)
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


def _retrieve(question: str, filters: dict) -> list[RetrievedChunk]:
    with get_db() as db:
        return _retriever.retrieve(
            db,
            query=question,
            source_types=filters.get("source_types"),
            tag_filters=filters.get("tags"),
            top_k=5,
        )


def _single_item_context(item_id: str) -> tuple[str, list[RetrievedChunk]]:
    """Build the system prompt for chatting with one item; no citations."""
    item = library.get_item(item_id)
    if item is None:
        raise ValueError("Item not found.")
    return ITEM_CHAT_SYSTEM_PROMPT.format(context=format_item_context(item)), []
