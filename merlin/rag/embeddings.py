"""Pluggable embedding + reranking backend for hybrid semantic search.

Mirrors `config.py`'s lazy-LLM convention: nothing here is constructed at import
and importing this module never requires an API key. `get_embedder()` reads
`settings.embedding_provider` and returns:

- `NullEmbedder` when the provider is "none" (or the Jina key is missing) — it
  yields no vectors, so the retriever's vector arm produces nothing and the
  search degrades to the historical pure-FTS5 ranking. This is the safety
  default and the regression guard.
- `JinaEmbedder` when the provider is "jina" — hosted embeddings + reranking over
  HTTP (see `docs/JINA_API_REFERENCE.md`). Network errors propagate to callers,
  which all wrap embedder use in try/except and fall back to FTS5.

Jina v5 is **asymmetric**: documents are embedded at `retrieval.passage` and the
live search query at `retrieval.query`. `embed(..., query=True)` picks the query
task; everything else is a passage. Vectors are requested `normalized=True`, so
cosine similarity is a plain dot product downstream.
"""

from __future__ import annotations

from functools import lru_cache
import json
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import requests

from merlin.config import settings
from merlin.core.rate_limit import MinIntervalRateLimiter

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_EMBED_URL = "https://api.jina.ai/v1/embeddings"
_RERANK_URL = "https://api.jina.ai/v1/rerank"
# Network timeout (seconds) for a single Jina call. Generous enough for a small
# batch, short enough that a hung request can't stall a chat turn for long.
_TIMEOUT = 30.0

# Process-wide spacing between Jina calls across the ingest worker threads, the
# same burst guard the YouTube transcript endpoint uses. Default 0 (off) ⇒
# wait() is a no-op, so neither ingest nor the interactive search path pays any
# cost unless jina_min_interval is configured (e.g. on a free key).
_rate_limiter = MinIntervalRateLimiter(settings.jina_min_interval, name="jina")


@runtime_checkable
class Embedder(Protocol):
    """Embedding + (optional) reranking backend."""

    enabled: bool
    model: str

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        """Return one vector per input text (empty list when disabled)."""
        ...

    def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[tuple[int, float]] | None:
        """Return `(original_index, score)` pairs sorted by relevance, or None
        when reranking is unavailable (caller keeps its existing order)."""
        ...


class NullEmbedder:
    """No-op backend: pure FTS5 behaviour. Used when no provider is configured."""

    enabled = False
    model = ""

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        return []

    def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[tuple[int, float]] | None:
        return None


class JinaEmbedder:
    """Hosted Jina embeddings + reranking. Constructed only via `get_embedder()`
    when a key is present; methods raise on HTTP/parse errors and callers fall
    back to FTS5."""

    enabled = True

    def __init__(self, api_key: str, model: str, reranker_model: str) -> None:
        self._api_key = api_key
        self.model = model
        self._reranker_model = reranker_model

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        _rate_limiter.wait()
        resp = requests.post(
            _EMBED_URL,
            headers=self._headers,
            json={
                "model": self.model,
                # v5 is asymmetric — query side vs document side differ.
                "task": "retrieval.query" if query else "retrieval.passage",
                "normalized": True,
                "input": list(texts),
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        # Honour the index the API returns rather than assuming order.
        ordered = sorted(data, key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in ordered]

    def rerank(
        self, query: str, documents: list[str], *, top_n: int | None = None
    ) -> list[tuple[int, float]] | None:
        if not documents:
            return []
        payload: dict = {
            "model": self._reranker_model,
            "query": query,
            "documents": list(documents),
            # We already hold the docs by index; only need indices + scores.
            "return_documents": False,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        _rate_limiter.wait()
        resp = requests.post(
            _RERANK_URL, headers=self._headers, json=payload, timeout=_TIMEOUT
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        # Already sorted by relevance descending; map back to our indices.
        return [(r["index"], float(r["relevance_score"])) for r in results]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Return the configured embedder (cached). Falls back to `NullEmbedder`
    when the provider is "none" or the Jina key is missing."""
    if settings.embedding_provider == "jina" and settings.jina_api_key:
        return JinaEmbedder(
            api_key=settings.jina_api_key,
            model=settings.jina_embedding_model,
            reranker_model=settings.jina_reranker_model,
        )
    return NullEmbedder()


def item_embed_text(
    title: str | None, summary: str | None, tags: list[str] | None
) -> str:
    """Build the single document string embedded per library item.

    Per the chosen scope we embed the item's *gist* — title + tags + summary —
    not transcript chunks (FTS5 still covers transcript keywords). Empty parts
    are dropped so a tagless or untitled item still produces clean text.
    """
    parts: list[str] = []
    if title:
        parts.append(title.strip())
    if tags:
        parts.append(" ".join(t for t in tags if t))
    if summary:
        parts.append(summary.strip())
    return "\n".join(p for p in parts if p)


def store_item_embedding(
    session: Session,
    *,
    item_id: str,
    title: str | None,
    summary: str | None,
    tags: list[str] | None,
    embedder: Embedder | None = None,
) -> bool:
    """Embed one item's gist and upsert it into the `embeddings` table.

    Shared by the ingest hook and the backfill script. Returns False (a no-op)
    under `NullEmbedder` or when the item has no embeddable text. Does not commit
    — the caller owns the transaction. Raises on a Jina error so callers can
    decide whether to retry or skip.
    """
    embedder = embedder or get_embedder()
    if not embedder.enabled:
        return False
    text = item_embed_text(title, summary, tags)
    if not text:
        return False
    vectors = embedder.embed([text], query=False)
    if not vectors or not vectors[0]:
        return False

    # Local import avoids importing the db layer at module import time.
    from merlin.db.repositories.knowledge import EmbeddingRepository

    EmbeddingRepository.upsert(
        session,
        knowledge_item_id=item_id,
        chunk_index=0,
        chunk_text=text,
        embedding=json.dumps(vectors[0]),
        embedding_model=embedder.model,
    )
    return True
