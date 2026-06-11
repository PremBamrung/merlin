"""
Chat service — RAG over the knowledge base.

`answer()` retrieves relevant chunks via FTS5, builds the prompt, and returns a
(token_generator, citations) pair. The UI streams the generator with
`st.write_stream` and renders the citations afterwards — no SSE, no HTTP.
"""

from collections.abc import Iterator

from merlin.config import settings
from merlin.db.engine import get_db
from merlin.rag.prompts import MERLIN_SYSTEM_PROMPT, format_context
from merlin.rag.retriever import HybridRetriever, RetrievedChunk

_retriever = HybridRetriever()


def answer(
    question: str,
    history: list[dict] | None = None,
    filters: dict | None = None,
) -> tuple[Iterator[str], list[RetrievedChunk]]:
    """Return (token_generator, citations).

    history: prior turns as [{"role": "user"|"assistant", "content": str}, ...]
    filters: optional {"source_types": [...], "tags": [...]}
    """
    history = history or []
    filters = filters or {}

    with get_db() as db:
        chunks = _retriever.retrieve(
            db,
            query=question,
            source_types=filters.get("source_types"),
            tag_filters=filters.get("tags"),
            top_k=5,
        )

    messages = [
        {
            "role": "system",
            "content": MERLIN_SYSTEM_PROMPT.format(context=format_context(chunks)),
        },
        *history,
        {"role": "user", "content": question},
    ]

    def token_stream() -> Iterator[str]:
        for chunk in settings.llm.stream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if content:
                yield content

    return token_stream(), chunks
