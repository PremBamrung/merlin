# Vector / Semantic Search

**Status: shipped.** Hybrid retrieval (FTS5 keyword + vector semantic, fused with
RRF, refined by a Jina rerank pass) is implemented and live-tested against the
Jina API. This doc is the authoritative reference for *how it works, how it
scales, and how to operate it*. The original design rationale is in
`CHAT_AGENT_RETRIEVAL_PLAN.md` §"Fix 3"; the Jina wire format is in
`JINA_API_REFERENCE.md`.

---

## Pipeline

`search_library` (the chat agent tool) → `HybridRetriever.retrieve()`:

```
query
  ├── FTS5 lexical arm   (bm25 over knowledge_fts, tokenized OR-of-prefixes)
  └── vector arm         (cosine over per-item embeddings; inert without a provider)
        ↓
   RRF fusion            (Σ 1/(k+rank), k=60 — fuses by rank, not score)
        ↓
   Jina rerank           (precision pass over the top ~20 fused candidates)
        ↓
   top-k
```

- **RRF over score-blending** because bm25 (negative, unbounded) and cosine (0–1)
  live on incompatible scales; fusing by rank position needs no normalization.
- **Both arms degrade gracefully.** With `EMBEDDING_PROVIDER=none`, or on *any*
  Jina error, `vec_hits` is empty and the rerank is skipped, so `retrieve()`
  returns exactly the historical FTS5-only ranking. This is the safety property
  and is covered by a regression test.

Code: `merlin/rag/retriever.py` (`_fts` / `_vector` / `_rrf` / `_rerank`),
`merlin/rag/embeddings.py` (backends + factory).

---

## What gets embedded

**One vector per item**, built from `title + tags + summary` (see
`item_embed_text`). **Transcripts are *not* chunked or embedded.** Rationale:

- Cheap to embed and store (1 vector/item, ~200K tokens to backfill the whole
  corpus — trivially within Jina's free credits).
- FTS5 already covers transcript-level keyword matches; the vector arm adds
  *semantic* matching on each item's gist.
- The cost is no semantic matching on transcript *detail* (a concept discussed
  mid-video but absent from the summary). If that ever matters, transcript
  chunking (~512-token chunks, `chunk_index > 0`) is the upgrade — the schema and
  retriever already allow multiple chunks per item.

Vectors are **model-bound**: `embedding_model` is stored per row. The query must
be embedded with the same model as the documents. If you change
`JINA_EMBEDDING_MODEL`, **re-run the backfill** — otherwise the query is compared
against vectors from a different model. (The retriever does not currently filter
by model, so a half-migrated table degrades silently.)

---

## Precompute model

Document vectors are **precomputed once, offline, and cached**. The only live
calls per chat search are the query embedding and the rerank.

| When | Call | Frequency |
|------|------|-----------|
| **Ingest** (`services.ingest._index_for_search`) | embed the new item | once per item, ever |
| **Backfill** (`scripts/backfill_embeddings.py`) | embed existing items | one-time / after a model change |
| **Chat search** (`_vector`) | embed the **query only** | 1 per search |
| **Chat search** (`_rerank`) | rerank the ~20 candidates | 1 per search — *not cacheable* (query-dependent) |

Item/document vectors are never re-embedded on read.

---

## How the DB actually does vector search

**SQLite is a blob store here — it does not do the vector math.** There is **no
vector index, no ANN, no SQL-level similarity operator.**

- `embeddings.embedding` holds each vector as a **JSON text array**.
- On each query, `EmbeddingRepository.candidates_for_search` **loads every stored
  vector into Python** (optionally filtered by `source_type` in SQL).
- `_vector` then `json.loads` each one and computes cosine in **pure Python**,
  sorts, and takes top-N.

So the algorithm is **exact brute-force k-NN (a "flat" index)** — a full linear
scan, **O(N·d)** per query, **100% recall** (no approximation to tune). At one
vector per item, vector count = item count.

This is a deliberate choice for the current scale (`CHAT_AGENT_RETRIEVAL_PLAN.md`
§3b: *"brute-force cosine over loaded vectors is fine; note `sqlite-vec` as the
scale-up option"*). The dominant cost is **re-parsing all vectors from JSON text
on every query**, not the cosine FLOPs.

---

## Scaling

Brute force scales **linearly** with item count. Prod is ~1,000 items growing
**~150/week** (~7,800/year). Estimated vector-arm latency per query (pure-Python,
JSON-parse-bound):

| Time | ~Items | Est. vector-arm latency/query |
|------|--------|-------------------------------|
| now | 1,000 | ~0.3–0.5 s |
| +6 months | ~4,900 | ~1.5–2.5 s |
| +1 year | ~8,800 | ~3–5 s |

It runs alongside the (multi-second) LLM round-trip, so it's **fine now and for
the next few months**, but at this growth rate it becomes a noticeable drag
within ~6 months and unacceptable for chat within ~a year.

### Scale-up path (cheapest first)

| Option | What it buys | Cost | Leaves SQLite? |
|--------|-------------|------|----------------|
| **float32 `BLOB` + numpy** | Drops JSON parsing; one cached in-memory `(N×d)` matrix, vectorized dot product. Still exact. Comfortable to **hundreds of thousands** of vectors. | ~half a day + a migration + numpy dep | yes |
| **[`sqlite-vec`](https://github.com/asg017/sqlite-vec)** | `vec0` virtual table, SIMD brute force in C, moving toward ANN. | extension dependency | yes |
| **pgvector** | True ANN (HNSW/IVFFlat), sublinear. | **Postgres migration** | no |

**Recommended next step: float32-BLOB + numpy**, done proactively in the next few
months (or when query latency first becomes noticeable). It removes the actual
bottleneck without leaving SQLite or adding approximation. The retriever's public
API, RRF, and rerank logic stay identical.

### On switching databases

Migrating to Postgres + pgvector for vector search *alone* is a poor trade: the
app is built around SQLite as a feature (single file, WAL, **FTS5** keyword arm,
SQLite-specific Alembic migrations, a Docker-volume DB you back up by copying).
Moving would also mean rewriting the FTS5 arm (→ `tsvector`) and operating a
server. **Move to Postgres only when something *other than* vector search
justifies it** (multi-user, concurrent writers, managed hosting) — then pgvector
comes along for free. Until then, BLOB+numpy or `sqlite-vec` covers you well into
hundreds of thousands of vectors.

---

## Embedder backends

`merlin/rag/embeddings.py`, built lazily via `get_embedder()` (mirrors the
lazy-LLM convention — importing the module never needs an API key):

- **`NullEmbedder`** — `EMBEDDING_PROVIDER=none` (or no Jina key). `enabled=False`;
  `embed()` returns `[]`, `rerank()` returns `None`. The retriever's vector +
  rerank arms become no-ops → pure FTS5. This is the default and the regression
  guard.
- **`JinaEmbedder`** — `EMBEDDING_PROVIDER=jina`. Hosted embeddings + reranking
  over HTTP. v5 is **asymmetric**: documents at `retrieval.passage`,
  the live query at `retrieval.query`; `normalized=true` so cosine is a dot
  product. Methods raise on HTTP/parse errors; all callers catch and fall back.

---

## Rate limiting

Jina free key ≈ **100 RPM / 100K TPM / 2 concurrent**; paid ≈ 500 RPM / 2M TPM;
premium ≈ 5,000 RPM / 50M TPM. Embeddings + reranker share the key and limits.

The three call paths are handled differently, on purpose:

| Path | Volume | On 429 | Throttling |
|------|--------|--------|-----------|
| **Chat query** (`_vector` + `_rerank`) | 2 calls/search | falls back to FTS5 instantly | **fail-fast — no retry/block** (chat must stay responsive) |
| **Ingest hook** (3 worker threads) | 1 call/item | best-effort, swallowed; backfill recovers | **process-wide `MinIntervalRateLimiter`** (`JINA_MIN_INTERVAL`) |
| **Backfill script** | ~13 batched calls | **429/5xx retry with backoff** (honors `Retry-After`) | `--sleep` pacing |

- `JINA_MIN_INTERVAL` (config, **default `0.0` = off**) is the *same* burst guard
  the YouTube transcript endpoint uses (`youtube_subtitle_min_interval`). It
  spaces the ingest workers across threads. Because it only blocks when calls
  land closer than the interval, a lone chat query pays nothing. **On a free key,
  set `JINA_MIN_INTERVAL=0.7`.**
- No cooldown circuit-breaker is wired up (unlike YouTube's) — the FTS5 fallback
  already covers the query path. Add one if you want the backend to stop
  embedding entirely for a window after a hard block.

---

## Configuration (`.env`)

```
EMBEDDING_PROVIDER=jina            # "none" → NullEmbedder (pure FTS5); "jina" → cloud
JINA_API_KEY="jina_…"
JINA_EMBEDDING_MODEL="jina-embeddings-v5-text-small"   # 1024-d
JINA_RERANKER_MODEL="jina-reranker-v3"
JINA_MIN_INTERVAL=0.0              # secs between Jina calls (set ~0.7 on a free key)
```

Settings live in `merlin/config.py`. With `EMBEDDING_PROVIDER=none`, all of the
above are ignored and retrieval is pure FTS5.

---

## Operations — backfill

New items embed automatically at ingest. Backfill embeds the **existing** corpus
once. The engine binds to `settings.database_url` at import, so point it with the
env var (not a flag):

```bash
# preview (no API calls, no writes):
DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \
    uv run python scripts/backfill_embeddings.py --dry-run

# full run:
DATABASE_URL="sqlite:///<path>/merlin.db" \
    uv run python scripts/backfill_embeddings.py

# free-tier key (≈100K TPM): pace it
DATABASE_URL="sqlite:///<path>/merlin.db" \
    uv run python scripts/backfill_embeddings.py --sleep 12
```

- **Resumable:** skips items that already have a vector and commits per batch, so
  a 429/interrupt mid-run loses nothing — just re-run.
- Flags: `--batch N` (texts/call, default 64), `--limit N`, `--sleep S`,
  `--max-retries N` (default 5), `--dry-run`.
- **After a model change**, re-run it to re-embed every item with the new model.

---

## Tests

- `tests/backend/test_embeddings.py` — `item_embed_text`, `NullEmbedder`,
  `JinaEmbedder` request shape + parsing (HTTP mocked), the rate-limiter gate,
  `get_embedder` factory, RRF (pure function), the retriever's vector arm,
  FTS5-fallback-on-error, rerank reordering, and `store_item_embedding`.
- `tests/backend/conftest.py` forces `EMBEDDING_PROVIDER=none` so the suite never
  hits the live API; the Jina-path tests monkeypatch the embedder/HTTP boundary.
- **Live smoke test** (run once against the dev DB, rows cleaned up after):
  1024-d vectors; semantic cosine separated related (0.70) from unrelated (0.18);
  rerank ranked the relevant doc first; the integrated FTS+vector+RRF+rerank
  retrieve ran live and returned coherent results.
