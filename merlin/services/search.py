"""Unified library search — the ⌘K palette and the Library search box.

One engine for both: `HybridRetriever` (FTS5 keyword + vector meaning, fused
with RRF, then the optional Jina rerank — see docs/VECTOR_SEARCH.md), with
each hit hydrated into the same shape as a Library list item plus the matched
excerpt, its fused score and which arm found it. Relevance-ranked and capped
(no paging): it answers "find me that", the paged Library list answers
"browse". Without an embedding provider it is pure FTS5.
"""

from __future__ import annotations

from merlin.db.engine import SessionFactory
from merlin.db.models import KnowledgeItem
from merlin.rag.retriever import HybridRetriever
from merlin.services.library import serialize_item

MAX_RESULTS = 20


def search(
    query: str, limit: int = MAX_RESULTS, source_type: str | None = None
) -> dict:
    """``{"query", "items": [ListItem + excerpt/score/match]}``, best first."""
    from merlin.db.repositories.topics import TopicRepository

    q = (query or "").strip()
    if not q:
        return {"query": q, "items": []}
    limit = max(1, min(limit, MAX_RESULTS))
    with SessionFactory() as session:
        hits = HybridRetriever().search(
            session,
            q,
            source_types=[source_type] if source_type else None,
            top_k=limit,
        )
        ids = [chunk.knowledge_item_id for chunk, _ in hits]
        rows = session.query(KnowledgeItem).filter(KnowledgeItem.id.in_(ids)).all()
        by_id = {row.id: row for row in rows}
        assignments = TopicRepository.assignments_for_items(session, ids)
        items = []
        for chunk, match in hits:
            row = by_id.get(chunk.knowledge_item_id)
            if row is None:
                continue
            item = serialize_item(row, topics=assignments.get(row.id, []))
            item.update(excerpt=chunk.excerpt, score=chunk.score, match=match)
            items.append(item)
    return {"query": q, "items": items}
