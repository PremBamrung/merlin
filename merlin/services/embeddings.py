"""Embedding self-heal — fill vectors for items that are missing them.

Single source of truth for the backfill, shared by:
- the startup auto-heal (api.main spawns a daemon thread calling
  `heal_missing_embeddings()`), and
- the CLI `scripts/backfill_embeddings.py`.

New items embed themselves at ingest (`services.ingest._index_for_search`); this
covers the pre-existing backlog plus any item whose ingest-time embedding failed
(that path is best-effort and swallows errors). It is idempotent and cheap when
nothing is missing (one indexed query → no API calls), and a complete no-op when
no embedding provider is configured.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import time

import requests

from merlin.core.logging import logger
from merlin.db.engine import SessionFactory
from merlin.db.models import KnowledgeItem
from merlin.db.repositories.knowledge import EmbeddingRepository
from merlin.rag.embeddings import get_embedder, item_embed_text

# HTTP statuses worth retrying: 429 (rate limit) + transient 5xx.
_RETRYABLE = {429, 500, 502, 503, 504}


def pending_items(limit: int | None = None) -> list[dict]:
    """Completed items with no stored vector, as `{id, title, text}` dicts.

    `text` is the gist we embed (title + tags + summary); items with nothing
    embeddable are skipped.
    """
    with SessionFactory() as session:
        done = EmbeddingRepository.item_ids_with_embeddings(session)
        rows = (
            session.query(
                KnowledgeItem.id,
                KnowledgeItem.title,
                KnowledgeItem.summary,
                KnowledgeItem.tags,
            )
            .filter(KnowledgeItem.status == "completed")
            .order_by(KnowledgeItem.ingested_at)
            .all()
        )

    items: list[dict] = []
    for row in rows:
        if row[0] in done:
            continue
        try:
            tags = json.loads(row[3]) if row[3] else []
        except (ValueError, TypeError):
            tags = []
        text = item_embed_text(row[1], row[2], tags)
        if not text:
            continue
        items.append({"id": row[0], "title": row[1], "text": text})
        if limit and len(items) >= limit:
            break
    return items


def _embed_with_retry(
    embedder, texts: list[str], max_retries: int
) -> list[list[float]]:
    """Embed a batch, backing off on rate-limit/5xx errors.

    The interactive retriever fails fast to FTS5 on any Jina error (a chat query
    must not hang); the *backfill* is the opposite — it should wait out a 429 so
    a long run survives a low free-tier TPM cap. Honours `Retry-After` when
    present, else exponential backoff capped at 60s.
    """
    delay = 5.0
    for attempt in range(max_retries + 1):
        try:
            return embedder.embed(texts, query=False)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status not in _RETRYABLE or attempt == max_retries:
                raise
            retry_after = exc.response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else delay
            logger.warning(
                "Jina %s during embedding backfill; retrying in %.0fs (attempt %d/%d)",
                status,
                wait,
                attempt + 1,
                max_retries,
            )
            time.sleep(wait)
            delay = min(delay * 2, 60.0)
    raise RuntimeError("unreachable")  # loop always returns or raises


def heal_missing_embeddings(
    *,
    batch: int = 64,
    limit: int | None = None,
    max_retries: int = 5,
    sleep: float = 0.0,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Embed every completed item that lacks a vector. Returns a summary dict.

    No-op (returns `provider_enabled=False`) when no embedding provider is
    configured. `on_progress(done, total)` is called after each committed batch.
    Best-effort batching: one Jina embeddings call per `batch` items, with
    per-batch 429/5xx backoff, committed per batch so an interruption loses
    nothing (re-running skips what's already embedded).
    """
    embedder = get_embedder()
    if not embedder.enabled:
        return {"provider_enabled": False, "pending": 0, "embedded": 0}

    pending = pending_items(limit)
    total = len(pending)
    if not pending:
        return {"provider_enabled": True, "pending": 0, "embedded": 0}

    logger.info("Embedding self-heal: %d item(s) missing vectors.", total)
    done = 0
    for start in range(0, total, batch):
        chunk = pending[start : start + batch]
        vectors = _embed_with_retry(embedder, [it["text"] for it in chunk], max_retries)
        if len(vectors) != len(chunk):
            raise RuntimeError(
                f"Jina returned {len(vectors)} vectors for {len(chunk)} inputs"
            )
        with SessionFactory() as session:
            for it, vec in zip(chunk, vectors, strict=True):
                EmbeddingRepository.upsert(
                    session,
                    knowledge_item_id=it["id"],
                    chunk_index=0,
                    chunk_text=it["text"],
                    embedding=json.dumps(vec),
                    embedding_model=embedder.model,
                )
            session.commit()
        done += len(chunk)
        if on_progress:
            on_progress(done, total)
        if sleep and start + batch < total:
            time.sleep(sleep)

    logger.info("Embedding self-heal: embedded %d item(s).", done)
    return {"provider_enabled": True, "pending": total, "embedded": done}
