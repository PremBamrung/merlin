"""
HybridRetriever — FTS5 keyword search **fused with vector search** over the
knowledge base.

Two arms run independently and are combined with **Reciprocal Rank Fusion (RRF)**:

- **FTS5 (lexical).** The query is tokenized into an OR-of-prefixes FTS5
  expression (so a natural-language question matches on any of its content words
  instead of one verbatim phrase that almost never appears), ranked with weighted
  **bm25**, and each hit gets a real **snippet()** excerpt from the column that
  matched — including raw transcripts.
- **Vector (semantic).** The query is embedded once (see `merlin.rag.embeddings`)
  and compared by cosine against the per-item vectors in the `embeddings` table.
  Matches by meaning, so paraphrases hit even when no keyword overlaps.

RRF fuses by **rank position** (`Σ 1/(k+rank)`, k≈60) rather than score, so bm25
(negative, unbounded) and cosine (0–1) need no normalization. An optional **Jina
rerank** pass then reorders the fused candidates by a high-precision relevance
score before the top-k is returned.

The vector and rerank arms are **inert without a provider**: when the embedder is
`NullEmbedder` (or any Jina call errors), `vec_hits` is empty and the rerank is
skipped, so `retrieve()` returns exactly the historical FTS5 ranking.
"""

from dataclasses import dataclass
import json
import math
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from merlin.db.repositories.knowledge import EmbeddingRepository
from merlin.rag.embeddings import get_embedder

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

# RRF constant. Standard value; dampens the contribution of low ranks so the
# top of each list dominates the fused order.
_RRF_K = 60

# How many fused candidates feed the rerank pass (and the size of each arm's
# candidate pool before fusion). Reranking one call over ~20 docs is cheap and
# precise; larger pools cost more tokens for diminishing recall.
_RERANK_POOL = 20


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


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Vectors are requested normalized, but normalize again
    defensively so a non-normalized store can't skew the ranking."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _tags_excluded(tags: str | None, tag_filters: list[str] | None) -> bool:
    """True when `tag_filters` is set and this item's (JSON-text) tags don't
    contain any of them — the shared post-hoc tag filter for both arms."""
    if not tag_filters:
        return False
    if not tags:
        return True
    return not any(t in tags for t in tag_filters)


class HybridRetriever:
    """FTS5 + vector retrieval fused with RRF, with an optional Jina rerank.

    `retrieve()` keeps the same signature it always had; hybridisation happens
    inside. With no embedding provider configured the vector/rerank arms are
    no-ops and the result is identical to the prior FTS5-only ranking.
    """

    def retrieve(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None = None,
        tag_filters: list[str] | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        top_k = max(1, top_k)
        # Each arm contributes a pool of candidates; fuse, rerank, then trim.
        pool = max(top_k, _RERANK_POOL)
        fts_hits = self._fts(session, query, source_types, tag_filters, pool)
        vec_hits = self._vector(session, query, source_types, tag_filters, pool)
        fused = self._rrf(fts_hits, vec_hits, top_k=_RERANK_POOL)
        reranked = self._rerank(query, fused)
        return reranked[:top_k]

    # -- arm 1: lexical (FTS5 + bm25) ------------------------------------- #
    def _fts(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None,
        tag_filters: list[str] | None,
        limit: int,
    ) -> list[RetrievedChunk]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        weights = ", ".join(str(w) for w in _BM25_WEIGHTS)
        # Over-fetch so post-hoc tag filtering (JSON column) still yields a full
        # pool after trimming.
        params: dict = {
            "q": fts_query,
            "snip": _SNIPPET_TOKENS,
            "limit": limit * 5,
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
            (
                item_id,
                source_type,
                source_id,
                title,
                author,
                summary,
                tags,
                published_at,
                excerpt,
                score,
            ) = row  # noqa: E501

            if _tags_excluded(tags, tag_filters):
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
            if len(chunks) >= limit:
                break

        return chunks

    # -- arm 2: semantic (vector cosine) --------------------------------- #
    def _vector(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None,
        tag_filters: list[str] | None,
        limit: int,
    ) -> list[RetrievedChunk]:
        embedder = get_embedder()
        if not embedder.enabled:
            return []
        try:
            qvecs = embedder.embed([query], query=True)
        except Exception:
            # Network/parse error — degrade to FTS5-only (no vector arm).
            return []
        if not qvecs or not qvecs[0]:
            return []
        qvec = qvecs[0]

        try:
            candidates = EmbeddingRepository.candidates_for_search(
                session, source_types
            )
        except Exception:
            return []

        scored: list[tuple[float, RetrievedChunk]] = []
        for c in candidates:
            if _tags_excluded(c.get("tags"), tag_filters):
                continue
            try:
                vec = json.loads(c["embedding"]) if c["embedding"] else None
            except (ValueError, TypeError):
                vec = None
            if not vec:
                continue
            sim = _cosine(qvec, vec)
            summary = c.get("summary") or ""
            excerpt = (summary[:300]).strip() or (c.get("chunk_text") or "")[:300]
            scored.append(
                (
                    sim,
                    RetrievedChunk(
                        knowledge_item_id=c["knowledge_item_id"],
                        source_type=c["source_type"],
                        source_id=c["source_id"],
                        title=c.get("title") or "",
                        author=c.get("author"),
                        excerpt=excerpt,
                        score=round(sim, 4),
                        published_at=_ymd(c.get("published_at")),
                    ),
                )
            )

        scored.sort(key=lambda t: t[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    # -- fusion ----------------------------------------------------------- #
    @staticmethod
    def _rrf(
        fts_hits: list[RetrievedChunk],
        vec_hits: list[RetrievedChunk],
        top_k: int,
        k: int = _RRF_K,
    ) -> list[RetrievedChunk]:
        """Reciprocal Rank Fusion over the two ranked lists, deduped by item.

        Each list contributes `1/(k + rank)` (0-based rank) to an item's score.
        The lexical chunk is preferred as the representative (it carries a
        matched snippet); a vector-only item falls back to its own chunk. When
        `vec_hits` is empty this preserves the FTS5 order exactly (scores stay
        strictly decreasing by rank) — the zero-provider safety property.
        """
        scores: dict[str, float] = {}
        rep: dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(fts_hits):
            iid = chunk.knowledge_item_id
            scores[iid] = scores.get(iid, 0.0) + 1.0 / (k + rank)
            rep.setdefault(iid, chunk)
        for rank, chunk in enumerate(vec_hits):
            iid = chunk.knowledge_item_id
            scores[iid] = scores.get(iid, 0.0) + 1.0 / (k + rank)
            rep.setdefault(iid, chunk)  # only used if FTS didn't supply one

        order = sorted(scores, key=lambda iid: scores[iid], reverse=True)
        fused: list[RetrievedChunk] = []
        for iid in order[:top_k]:
            chunk = rep[iid]
            chunk.score = round(scores[iid], 6)
            fused.append(chunk)
        return fused

    # -- precision pass (Jina rerank) ------------------------------------ #
    @staticmethod
    def _rerank(query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Reorder the fused candidates by Jina's relevance score. No-op (keeps
        the RRF order) when the provider is absent or the call errors."""
        embedder = get_embedder()
        if not embedder.enabled or len(chunks) < 2:
            return chunks
        documents = [f"{c.title}\n{c.excerpt}".strip() for c in chunks]
        try:
            results = embedder.rerank(query, documents, top_n=len(chunks))
        except Exception:
            return chunks
        if not results:
            return chunks
        reordered: list[RetrievedChunk] = []
        for idx, relevance in results:
            if 0 <= idx < len(chunks):
                chunk = chunks[idx]
                chunk.score = round(float(relevance), 4)
                reordered.append(chunk)
        return reordered or chunks

    def count(
        self,
        session: Session,
        query: str,
        source_types: list[str] | None = None,
    ) -> int:
        """Total items matching `query` (+ optional source_type) — a coverage
        signal for the caller. Mirrors the FTS MATCH/source filter only; the
        vector arm and tag filtering (post-hoc, JSON column) are intentionally
        not reflected here.
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
