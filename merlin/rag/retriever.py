"""
HybridRetriever — FTS5 keyword search over the knowledge base.

The query is **tokenized** into an OR-of-prefixes FTS5 expression (so a
natural-language question matches on any of its content words, instead of being
run as one verbatim phrase that almost never appears in the index), ranked with
weighted **bm25**, and each hit gets a real **snippet()** excerpt drawn from
whichever column actually matched — including raw transcripts, which the old
phrase query never surfaced.

Phase 3 will add vector/semantic search + Reciprocal Rank Fusion.
"""

from dataclasses import dataclass
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

# FTS5 column order in `knowledge_fts` (see migration 001): title, summary,
# raw_content, tags. bm25() weights are positional and follow this order —
# title and tags matter more than a stray word deep in a transcript.
_FTS_COLUMNS = ("title", "summary", "raw_content", "tags")
_BM25_WEIGHTS = (10.0, 5.0, 1.0, 8.0)

# A snippet window (in tokens) for the excerpt; ~32 reads like a sentence or two.
_SNIPPET_TOKENS = 32

# FTS5 reserves these as query syntax; we tokenize to bare words so they never
# reach the parser, but keep the set documented for anyone extending this.
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class RetrievedChunk:
    knowledge_item_id: str
    source_type: str
    source_id: str
    title: str
    author: str | None
    excerpt: str  # relevant excerpt (snippet) from the matched column
    score: float = 1.0
    published_at: str | None = None  # YYYY-MM-DD, when known


def _ymd(value) -> str | None:
    """Format a DB datetime/ISO-string to YYYY-MM-DD (date only), or None."""
    if not value:
        return None
    s = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return s[:10]


class HybridRetriever:
    """
    FTS5 keyword retrieval (Phase 1: keyword only).

    Searches title + summary + raw_content + tags via the `knowledge_fts`
    virtual table maintained by triggers, ranks with weighted bm25, and returns
    a `snippet()` excerpt per hit.
    """

    def retrieve(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None = None,
        tag_filters: list[str] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        # bm25() weights argument list, one per FTS column.
        weights = ", ".join(str(w) for w in _BM25_WEIGHTS)
        # Over-fetch so Python-side tag filtering (JSON column) still yields a
        # full page after trimming.
        params: dict = {
            "q": fts_query,
            "snip": _SNIPPET_TOKENS,
            "limit": top_k * 5,
        }

        # source_type is filtered in SQL (parameterised IN-list) when provided,
        # so the candidate pool is the right shape before ranking.
        source_clause = ""
        if source_types:
            placeholders = ", ".join(f":st{i}" for i in range(len(source_types)))
            source_clause = f"AND ki.source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st{i}"] = st

        # colnum -1 → snippet() auto-picks the first column with a match, so a
        # transcript hit yields a transcript excerpt, a title hit a title one.
        sql = text(
            f"""
            SELECT ki.id, ki.source_type, ki.source_id, ki.title, ki.author,
                   ki.summary, ki.tags, ki.published_at,
                   snippet(knowledge_fts, -1, '', '', '…', :snip) AS excerpt,
                   bm25(knowledge_fts, {weights}) AS score
            FROM knowledge_items ki
            JOIN knowledge_fts fts ON ki.rowid = fts.rowid
            WHERE knowledge_fts MATCH :q
              AND ki.status = 'completed'
              {source_clause}
            ORDER BY score
            LIMIT :limit
            """
        )

        rows = session.execute(sql, params).fetchall()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            item_id, source_type, source_id, title, author, summary, tags, published_at, excerpt, score = row  # noqa: E501

            # Tag filter — tags are JSON text; keep the simple substring check.
            if tag_filters and tags:
                if not any(t in tags for t in tag_filters):
                    continue
            elif tag_filters and not tags:
                continue

            # bm25 returns a negative score (more relevant = more negative);
            # flip it so larger = more relevant for any downstream display.
            excerpt = (excerpt or "").strip() or (summary or "")[:300]
            chunks.append(
                RetrievedChunk(
                    knowledge_item_id=item_id,
                    source_type=source_type,
                    source_id=source_id,
                    title=title or "",
                    author=author,
                    excerpt=excerpt,
                    score=round(-float(score), 4),
                    published_at=_ymd(published_at),
                )
            )
            if len(chunks) >= top_k:
                break

        return chunks

    def count(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None = None,
    ) -> int:
        """Total items matching `query` (+ optional source_type) — a coverage
        signal for the caller. Mirrors `retrieve`'s MATCH/source filter; tag
        filtering (post-hoc, JSON column) is intentionally not reflected here.
        """
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return 0
        params: dict = {"q": fts_query}
        source_clause = ""
        if source_types:
            placeholders = ", ".join(f":st{i}" for i in range(len(source_types)))
            source_clause = f"AND ki.source_type IN ({placeholders})"
            for i, st in enumerate(source_types):
                params[f"st{i}"] = st
        sql = text(
            f"""
            SELECT count(*)
            FROM knowledge_items ki
            JOIN knowledge_fts fts ON ki.rowid = fts.rowid
            WHERE knowledge_fts MATCH :q
              AND ki.status = 'completed'
              {source_clause}
            """
        )
        return int(session.execute(sql, params).scalar() or 0)

    @staticmethod
    def _build_fts_query(query: str) -> str:
        """Tokenize a natural-language query into an OR-of-prefixes FTS5 match.

        "What are DJI's moats?" → `dji* OR moats* OR what* OR are*`. Bare word
        tokens only (extracted with `\\w+`), so no FTS5 query operator can leak
        in from user text. Returns "" when there are no usable tokens.
        """
        tokens = _WORD_RE.findall(query.lower())
        # Drop 1-char tokens (mostly noise / stray letters); keep digits.
        tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
        if not tokens:
            return ""
        # De-dup while preserving order so a repeated word doesn't skew bm25.
        seen: set[str] = set()
        unique = [t for t in tokens if not (t in seen or seen.add(t))]
        return " OR ".join(f"{t}*" for t in unique)
