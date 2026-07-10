"""
KnowledgeItemRepository — CRUD for knowledge_items + youtube_metadata.
All methods are synchronous; session is passed in (FastAPI Depends pattern).
"""

from datetime import UTC, datetime
import difflib
import re

from sqlalchemy import or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from merlin.db.models import (
    Embedding,
    ItemTopic,
    KnowledgeItem,
    Topic,
    YouTubeMetadata,
)

# Fuzzy fallback only runs when an exact search finds nothing and is reserved
# for queries long enough that a close match is meaningful (avoids "ai"-style
# noise). Similarity is difflib's ratio; ~0.72 catches single-char typos
# ("ep32"→"esp32") without matching unrelated words.
_FUZZY_MIN_LEN = 4
_FUZZY_THRESHOLD = 0.72

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _searchable_tokens(search: str) -> list[str]:
    """Whitespace tokens that carry at least one alphanumeric char."""
    return [t for t in search.split() if any(c.isalnum() for c in t)]


def _build_fts_match(search: str, include_transcript: bool) -> str | None:
    """Turn raw user input into a safe FTS5 prefix MATCH query.

    Each token becomes a quoted prefix term (``"tok"*``): the quotes neutralise
    FTS5 syntax characters (so ``C++`` or a stray quote can't raise a syntax
    error), and the trailing ``*`` makes it match as you type. Unless
    ``include_transcript`` is set, the match is scoped to title/summary/tags
    with a column filter (the transcript column ``raw_content`` is excluded) —
    parentheses are required so the filter applies to *every* term, not just the
    first. Returns ``None`` when no usable token remains.
    """
    terms: list[str] = []
    for raw in _searchable_tokens(search):
        escaped = raw.replace('"', '""')
        terms.append(f'"{escaped}"*')
    if not terms:
        return None
    joined = " ".join(terms)
    if include_transcript:
        return joined
    return f"{{title summary tags}} : ({joined})"


def _fuzzy_match_ids(
    candidates: list[tuple[str, str | None]], tokens: list[str]
) -> list[str]:
    """Rank candidate (id, title) pairs by fuzzy similarity to the query tokens.

    Each query token must find a sufficiently similar *word* in the title; the
    item's score is the weakest such per-token match (so every token has to land
    somewhere). Returns ids whose score clears the threshold, best first.
    """
    q_tokens = [t.lower() for t in tokens]
    scored: list[tuple[float, str]] = []
    for item_id, title in candidates:
        if not title:
            continue
        words = [w.lower() for w in _WORD_RE.findall(title)]
        if not words:
            continue
        per_token = [
            max(
                (difflib.SequenceMatcher(None, qt, w).ratio() for w in words),
                default=0.0,
            )
            for qt in q_tokens
        ]
        score = min(per_token)
        if score >= _FUZZY_THRESHOLD:
            scored.append((score, item_id))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [item_id for _, item_id in scored]


class KnowledgeItemRepository:
    @staticmethod
    def create(session: Session, data: dict) -> KnowledgeItem:
        """Insert a new KnowledgeItem. Returns the saved instance."""
        item = KnowledgeItem(**data)
        session.add(item)
        session.flush()  # get generated id without committing
        return item

    @staticmethod
    def get_by_id(session: Session, item_id: str) -> KnowledgeItem | None:
        return session.get(KnowledgeItem, item_id)

    @staticmethod
    def get_by_source(
        session: Session, source_type: str, source_id: str
    ) -> KnowledgeItem | None:
        return (
            session.query(KnowledgeItem)
            .filter_by(source_type=source_type, source_id=source_id)
            .first()
        )

    @staticmethod
    def list_all(
        session: Session,
        source_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
        topics: list[str] | None = None,
        read: bool | None = None,
        saved: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "newest",
        search_transcripts: bool = False,
    ) -> tuple[list[KnowledgeItem], int]:
        """Return (items, total_count) with optional filters.

        read/saved: None = no filter; True/False match presence of the
        corresponding timestamp (read_at / saved_at).
        topics: list of topic slugs to include. The sentinel ``"uncategorised"``
        matches items with no item_topics row. Mixing the sentinel with real
        slugs is OR semantics: ``slug IN (...) OR (has no item_topics rows)``.
        sort: newest | oldest | longest | title | relevance
        search_transcripts: when True, search also matches full transcript text
        (raw_content); otherwise search is scoped to title/summary/tags.

        The topic/tag/status filters are applied to the base query *before* the
        search branch, so they hold on every downstream path — the plain sort,
        the fuzzy-title fallback, and the separate ``sort="relevance"`` re-query.
        """
        q = session.query(KnowledgeItem)

        if source_type:
            q = q.filter(KnowledgeItem.source_type == source_type)
        if status:
            q = q.filter(KnowledgeItem.status == status)
        if read is not None:
            q = q.filter(
                KnowledgeItem.read_at.isnot(None)
                if read
                else KnowledgeItem.read_at.is_(None)
            )
        if saved is not None:
            q = q.filter(
                KnowledgeItem.saved_at.isnot(None)
                if saved
                else KnowledgeItem.saved_at.is_(None)
            )
        if tags:
            # Match the JSON-quoted form ("ai" not ai) so a substring like "ai"
            # doesn't match "ai-safety". Both write paths store tags via
            # json.dumps, so the quotes are always present; filter values come
            # from list_tags (exact stored strings).
            for tag in tags:
                q = q.filter(KnowledgeItem.tags.contains(f'"{tag}"'))
        if topics:
            real = [s for s in topics if s != "uncategorised"]
            want_uncat = "uncategorised" in topics
            conds = []
            if real:
                assigned_to_slug = (
                    select(ItemTopic.knowledge_item_id)
                    .join(Topic, Topic.id == ItemTopic.topic_id)
                    .where(
                        ItemTopic.knowledge_item_id == KnowledgeItem.id,
                        Topic.slug.in_(real),
                    )
                )
                conds.append(assigned_to_slug.exists())
            if want_uncat:
                any_topic = select(ItemTopic.knowledge_item_id).where(
                    ItemTopic.knowledge_item_id == KnowledgeItem.id
                )
                conds.append(~any_topic.exists())
            if conds:
                q = q.filter(or_(*conds))
        # Keyword search. `ordered_ids` is the match set in best-first order
        # (bm25, or fuzzy similarity for the fallback) — used directly when
        # sort="relevance", or as an `IN (...)` filter for the other sorts.
        ordered_ids: list[str] | None = None
        if search:
            fts_match = _build_fts_match(search, search_transcripts)
            if fts_match is None:
                return [], 0
            try:
                # Weighted bm25 over (title, summary, raw_content, tags): a
                # title/summary hit outranks a passing transcript mention.
                rows = session.execute(
                    text(
                        "SELECT ki.id FROM knowledge_items ki "
                        "JOIN knowledge_fts fts ON ki.rowid = fts.rowid "
                        "WHERE knowledge_fts MATCH :q "
                        "ORDER BY bm25(knowledge_fts, 10.0, 4.0, 1.0, 4.0)"
                    ),
                    {"q": fts_match},
                ).fetchall()
            except OperationalError:
                # Malformed FTS expression — degrade to "no matches", no 500.
                return [], 0
            ordered_ids = [row[0] for row in rows]
            if not ordered_ids:
                # No exact hit — try a fuzzy pass over titles to rescue typos
                # (e.g. "ep32" → "esp32"), but only for long-enough queries.
                tokens = _searchable_tokens(search)
                if sum(len(t) for t in tokens) >= _FUZZY_MIN_LEN:
                    candidates = q.with_entities(
                        KnowledgeItem.id, KnowledgeItem.title
                    ).all()
                    ordered_ids = _fuzzy_match_ids(candidates, tokens)
                if not ordered_ids:
                    return [], 0
            q = q.filter(KnowledgeItem.id.in_(ordered_ids))

        # Relevance ranking only applies when there's an active search. With no
        # query, "relevance" is meaningless → fall through to the newest default.
        if sort == "relevance" and ordered_ids is not None:
            # Restrict the FTS match order to ids that pass the other filters,
            # then paginate by rank in Python (IN(...) doesn't preserve order).
            allowed = {row[0] for row in q.with_entities(KnowledgeItem.id).all()}
            final_ids = [i for i in ordered_ids if i in allowed]
            total = len(final_ids)
            page_ids = final_ids[(page - 1) * page_size : page * page_size]
            if not page_ids:
                return [], total
            by_id = {
                it.id: it
                for it in session.query(KnowledgeItem)
                .filter(KnowledgeItem.id.in_(page_ids))
                .all()
            }
            return [by_id[i] for i in page_ids if i in by_id], total

        order_by = {
            "newest": KnowledgeItem.ingested_at.desc(),
            "oldest": KnowledgeItem.ingested_at.asc(),
            "longest": KnowledgeItem.word_count.desc().nulls_last(),
            "title": KnowledgeItem.title.asc(),
        }.get(sort, KnowledgeItem.ingested_at.desc())

        total = q.count()
        items = (
            q.order_by(order_by).offset((page - 1) * page_size).limit(page_size).all()
        )
        return items, total

    @staticmethod
    def update(session: Session, item_id: str, updates: dict) -> KnowledgeItem | None:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        for k, v in updates.items():
            setattr(item, k, v)
        item.updated_at = datetime.now(UTC)
        return item

    @staticmethod
    def delete(session: Session, item_id: str) -> bool:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        session.delete(item)
        return True

    @staticmethod
    def set_read(session: Session, item_id: str, read: bool) -> KnowledgeItem | None:
        """Mark an item read (now) or unread (clear read_at). None if missing.

        Deliberately does NOT bump updated_at — read/save are consumption state,
        not content edits, and must not reorder content-sorted views.
        """
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        item.read_at = datetime.now(UTC) if read else None
        return item

    @staticmethod
    def set_saved(session: Session, item_id: str, saved: bool) -> KnowledgeItem | None:
        """Star (now) or un-star (clear saved_at) an item. None if missing."""
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        item.saved_at = datetime.now(UTC) if saved else None
        return item

    @staticmethod
    def count_unread(session: Session) -> int:
        """Completed items not yet read — the Feed queue size."""
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(KnowledgeItem.read_at.is_(None))
            .count()
        )

    @staticmethod
    def mark_all_read(session: Session) -> int:
        """Bulk-mark every completed, unread item read. Returns the count.

        Clears the Feed queue in one shot (also the one-time backfill so already
        ingested items count as 'already viewed').
        """
        return (
            session.query(KnowledgeItem)
            .filter(KnowledgeItem.status == "completed")
            .filter(KnowledgeItem.read_at.is_(None))
            .update(
                {KnowledgeItem.read_at: datetime.now(UTC)}, synchronize_session=False
            )
        )

    @staticmethod
    def clear_summary(session: Session, item_id: str) -> bool:
        """Clear summary fields only, keep raw_content and metadata."""
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        item.summary = None
        item.summary_length = None
        item.llm_model = None
        item.sections = None
        item.status = "pending"
        item.error_message = None
        item.updated_at = datetime.now(UTC)
        return True


class YouTubeMetadataRepository:
    @staticmethod
    def upsert(session: Session, knowledge_item_id: str, data: dict) -> YouTubeMetadata:
        existing = session.get(YouTubeMetadata, knowledge_item_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        meta = YouTubeMetadata(knowledge_item_id=knowledge_item_id, **data)
        session.add(meta)
        session.flush()
        return meta

    @staticmethod
    def get_by_video_id(session: Session, video_id: str) -> YouTubeMetadata | None:
        return session.query(YouTubeMetadata).filter_by(video_id=video_id).first()


class EmbeddingRepository:
    """Vector storage for semantic search. One row per (item, chunk_index);
    the current scope embeds one vector per item (chunk_index=0)."""

    @staticmethod
    def upsert(
        session: Session,
        knowledge_item_id: str,
        chunk_index: int,
        chunk_text: str,
        embedding: str,
        embedding_model: str,
    ) -> Embedding:
        existing = (
            session.query(Embedding)
            .filter_by(knowledge_item_id=knowledge_item_id, chunk_index=chunk_index)
            .first()
        )
        if existing:
            existing.chunk_text = chunk_text
            existing.embedding = embedding
            existing.embedding_model = embedding_model
            return existing
        row = Embedding(
            knowledge_item_id=knowledge_item_id,
            chunk_index=chunk_index,
            chunk_text=chunk_text,
            embedding=embedding,
            embedding_model=embedding_model,
        )
        session.add(row)
        session.flush()
        return row

    @staticmethod
    def candidates_for_search(
        session: Session, source_types: list[str] | None = None
    ) -> list[dict]:
        """Load every stored vector (with the item fields the retriever needs)
        for completed items, optionally restricted to `source_types`.

        SQLite has no native vector index; for the current corpus a brute-force
        cosine over these rows in Python is fine. `sqlite-vec` is the scale-up
        path if the library grows large.
        """
        q = (
            session.query(
                Embedding.knowledge_item_id,
                Embedding.embedding,
                Embedding.chunk_text,
                KnowledgeItem.source_type,
                KnowledgeItem.source_id,
                KnowledgeItem.title,
                KnowledgeItem.author,
                KnowledgeItem.summary,
                KnowledgeItem.tags,
                KnowledgeItem.published_at,
            )
            .join(KnowledgeItem, Embedding.knowledge_item_id == KnowledgeItem.id)
            .filter(KnowledgeItem.status == "completed")
        )
        if source_types:
            q = q.filter(KnowledgeItem.source_type.in_(source_types))
        cols = (
            "knowledge_item_id",
            "embedding",
            "chunk_text",
            "source_type",
            "source_id",
            "title",
            "author",
            "summary",
            "tags",
            "published_at",
        )
        return [dict(zip(cols, row, strict=True)) for row in q.all()]

    @staticmethod
    def item_ids_with_embeddings(session: Session) -> set[str]:
        """Ids of items that already have at least one stored vector (backfill
        skip-set)."""
        rows = session.query(Embedding.knowledge_item_id).distinct().all()
        return {r[0] for r in rows}
