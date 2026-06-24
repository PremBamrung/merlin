# Jina AI — Embeddings & Reranking Reference

Provider chosen for Merlin's hybrid semantic search (Fix 3 in
`CHAT_AGENT_RETRIEVAL_PLAN.md`). Jina is a **hosted** API — embeddings and rerank
are HTTP POST calls, no local model.

> **Secrets:** the API key lives only in `.env` (`JINA_API_KEY`, gitignored).
> Never commit the literal key — this doc uses the `$JINA_API_KEY` placeholder.

## Config (`.env`)

```
EMBEDDING_PROVIDER=jina            # "none" → NullEmbedder (pure FTS5); "jina" → cloud
JINA_API_KEY="jina_…"              # 10M free credits
JINA_EMBEDDING_MODEL="jina-embeddings-v5-text-small"
JINA_RERANKER_MODEL="jina-reranker-v3"
```

## Endpoints

| Purpose | URL | Model |
|---|---|---|
| Embeddings | `POST https://api.jina.ai/v1/embeddings` | `jina-embeddings-v5-text-small` |
| Reranking | `POST https://api.jina.ai/v1/rerank` | `jina-reranker-v3` |

Both require `Authorization: Bearer $JINA_API_KEY` and `Content-Type: application/json`.

Rate limits: <https://api.jina.ai/scalar#description/rate-limits> (check current RPM/TPM
before bulk backfill; chunk + space out requests).

---

## 1. Embeddings

**Asymmetric task types matter.** v5 encodes queries and documents differently —
use the right `task` on each side or retrieval quality drops:

- Indexing library items → `"task": "retrieval.passage"`
- Embedding the user's search query → `"task": "retrieval.query"`

Set `"normalized": true` so vectors are unit-length → cosine similarity is a plain
dot product.

### Request

```python
import requests

resp = requests.post(
    "https://api.jina.ai/v1/embeddings",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}",
    },
    json={
        "model": "jina-embeddings-v5-text-small",
        "task": "retrieval.passage",   # or "retrieval.query" for the search query
        "normalized": True,
        "input": [
            "First document text …",
            "Second document text …",
        ],
    },
)
data = resp.json()
```

### Response (shape)

```json
{
  "model": "jina-embeddings-v5-text-small",
  "object": "list",
  "usage": { "total_tokens": 123, "prompt_tokens": 123 },
  "data": [
    { "object": "embedding", "index": 0, "embedding": [0.01, -0.02, ...] },
    { "object": "embedding", "index": 1, "embedding": [ ... ] }
  ]
}
```

- `input` is a **list** — batch many texts per call to save round-trips.
- The vector **dimension** comes from the model; read `len(data[0]["embedding"])`
  and **store it alongside the vector** (the `embeddings.dim` column) rather than
  hardcoding — it lets us swap models without guessing.
- Bill is by `usage.total_tokens`; long transcripts must be **chunked** before
  embedding (don't embed a whole 30-min transcript as one string).

---

## 2. Reranking

Used as a precision pass **after** retrieval: take the fused candidate set
(FTS5 + vector via RRF), send the query + candidate texts to the reranker, and
reorder by its relevance scores. The reranker is the highest-precision signal but
costs one call per search, so run it on the merged top-N only (e.g. top 20 → keep
top `k`).

### Request

```python
import requests

resp = requests.post(
    "https://api.jina.ai/v1/rerank",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {JINA_API_KEY}",
    },
    json={
        "model": "jina-reranker-v3",
        "query": "Organic skincare products for sensitive skin",
        "top_n": 3,
        "documents": [
            "Organic skincare for sensitive skin …",
            "New makeup trends focus on bold colors …",
            "Bio-Hautpflege für empfindliche Haut …",
        ],
        "return_documents": False,   # we already hold the docs; only need indices+scores
    },
)
data = resp.json()
```

### Response (shape)

```json
{
  "model": "jina-reranker-v3",
  "usage": { "total_tokens": 456 },
  "results": [
    { "index": 0, "relevance_score": 0.92 },
    { "index": 2, "relevance_score": 0.71 },
    { "index": 1, "relevance_score": 0.05 }
  ]
}
```

- `results` is **sorted by relevance**, descending. `index` maps back into the
  `documents` array you sent — reorder your candidates by it.
- `return_documents: False` keeps the response small since we already have the
  source items by index.
- `top_n` caps how many results come back.

---

## Notes for the Merlin integration

- Both calls are network I/O on a synchronous plugin/service path — wrap in
  try/except and **degrade gracefully** (fall back to FTS5-only ranking) on error
  or missing key, exactly as `NullEmbedder` does today.
- Multilingual: both models are multilingual, which suits transcripts in mixed
  languages (the YouTube ingest already supports ~40 languages).
- Cache embeddings in the `embeddings` table; only the **query** is embedded live
  per search. Reranking can't be cached (query-dependent) — keep its candidate set
  small.
