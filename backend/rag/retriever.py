"""
HybridRetriever — FTS5 keyword search over the knowledge base.
Phase 3 will add vector/semantic search + Reciprocal Rank Fusion.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db.models import KnowledgeItem


@dataclass
class RetrievedChunk:
    knowledge_item_id: str
    source_type: str
    source_id: str
    title: str
    author: Optional[str]
    excerpt: str           # relevant excerpt from summary or raw_content
    score: float = 1.0


class HybridRetriever:
    """
    Two-stage retrieval (Phase 1: FTS5 only).

    SQLite FTS5 searches over:
        title + summary + raw_content + tags
    using the knowledge_fts virtual table maintained by triggers.
    """

    def retrieve(
        self,
        session: Session,
        query: str,
        source_types: Optional[list[str]] = None,
        tag_filters: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []

        # FTS5 MATCH query — escape special chars
        fts_query = self._escape_fts(query)

        sql = text(
            """
            SELECT ki.id, ki.source_type, ki.source_id, ki.title, ki.author,
                   ki.summary, ki.tags
            FROM knowledge_items ki
            JOIN knowledge_fts fts ON ki.rowid = fts.rowid
            WHERE knowledge_fts MATCH :q
              AND ki.status = 'completed'
            ORDER BY rank
            LIMIT :limit
            """
        )
        rows = session.execute(sql, {"q": fts_query, "limit": top_k * 3}).fetchall()

        chunks = []
        for row in rows:
            item_id, source_type, source_id, title, author, summary, tags = row

            # Apply source type filter
            if source_types and source_type not in source_types:
                continue

            # Apply tag filter (simple substring check)
            if tag_filters and tags:
                if not any(t in tags for t in tag_filters):
                    continue

            excerpt = (summary or "")[:500]
            chunks.append(
                RetrievedChunk(
                    knowledge_item_id=item_id,
                    source_type=source_type,
                    source_id=source_id,
                    title=title or "",
                    author=author,
                    excerpt=excerpt,
                )
            )
            if len(chunks) >= top_k:
                break

        return chunks

    @staticmethod
    def _escape_fts(query: str) -> str:
        """Escape FTS5 special characters for a simple phrase search."""
        # Wrap in quotes for phrase search, escape internal quotes
        sanitised = query.replace('"', '""')
        return f'"{sanitised}"'
