# Agentic Chat — Retrieval Fix Plan (items 1–3)

Implementation plan for the top three improvements from
`CHAT_IMPROVEMENTS_ANALYSIS.md`:

1. Expose publication dates + coverage counts in tool output
2. Transcript paging on `get_item`
3. Vector search (hybrid + RRF) — **scaffolding only, no real embedding API yet**

All three touch `merlin/rag/agent.py` and/or `merlin/rag/retriever.py`. None of
them touch the API or frontend (tool output is plain text that streams as-is).

> Not to be confused with `docs/CHAT_IMPROVEMENTS_PLAN.md`, which is the
> (already-shipped) chat-tab sidebar/UX plan. This doc is about the **retrieval
> layer** the agent uses.

---

## Two design questions answered first

### Q1. "Can't the 6-phrasings problem be solved by parallel searches in one step?"

**Partially — it's a worthwhile cheap mitigation, but not a replacement.**

- It's already *possible*: Pydantic AI lets the model emit several `search_library`
  calls in one step (parallel tool calls); nothing in `agent.py` disables that.
  The model just rarely chooses to. A system-prompt nudge ("when a question is
  broad, issue several focused searches with different vocabulary in one step")
  would get most of the latency win for free.
- **But it doesn't fix the mechanism.** Parallel searches are still *lexical*. If a
  document says "build multi-crit air/feu/terre" and never contains the word
  "stuff", more phrasings only help if the model *guesses* the right synonym.
  Semantic search matches by meaning, so the synonym problem disappears instead of
  being brute-forced.
- **It has real costs.** Each search's output is appended to history (tool results
  enter the context), so 6 parallel searches ≈ 6× token bloat and push against the
  `_over_budget` guard. And overlapping results need dedup/merge anyway — which is
  exactly what RRF does.

**Conclusion:** add the prompt nudge now (free recall boost), but treat vector
search as the actual fix. Parallel-lexical and semantic are complementary, not
substitutes.

### Q2. "With vector search, separate keyword vs vector tools, or hybrid with RRF?"

**One tool, hybrid under the hood, fused with Reciprocal Rank Fusion (RRF).**

- **RRF over score-blending** because bm25 (negative, unbounded) and cosine
  similarity (0–1) live on incompatible scales. RRF fuses by *rank position*, not
  score, so it needs no per-corpus normalization or tuning
  (`score = Σ 1/(k + rank_i)`, standard `k≈60`).
- **Keep keyword strength.** Lexical wins on exact tokens — proper nouns, version
  numbers ("3.6"), channel names, item names. Vector wins on paraphrase/concept.
  Hybrid keeps both; pure-vector would *regress* on exact-match queries.
- **One tool surface.** The agent is bad at choosing a retrieval mode and every
  extra tool/step bloats history. `search_library`'s signature stays the same;
  hybrid happens inside `HybridRetriever`. This is already the documented Phase-3
  plan (`retriever.py:11`, `:46`).

So: `search_library` → `HybridRetriever.retrieve()` runs FTS5 **and** vector
independently, fuses with RRF, trims to `top_k`. The embedding backend is behind a
swappable interface so no provider is committed yet (see Fix 3).

---

## Fix 1 — Dates + coverage counts in tool output

Data already flows into the tools; we're only changing formatting + one SQL select.

### 1a. `get_item` — `_format_item` (`agent.py:257`)
`library.get_item` → `serialize_item` already returns `published_at`, `channel`,
`views`, `duration` (`library.py:27,41-43`). Add them to the formatted output:

```python
# inside _format_item, after the author line:
if item.get("published_at"):
    lines.append(f"published: {item['published_at'][:10]}")   # YYYY-MM-DD
if item.get("duration"):
    lines.append(f"duration: {item['duration']}")
if item.get("views"):
    lines.append(f"views: {item['views']:,}")
```

### 1b. `browse_library` — `_format_browse` (`agent.py:278`)
Items come from `library.list_items` → `serialize_item`, so `published_at` is
present. Append the date to each row:

```python
row = f"[{it.get('id')}] {it.get('title') or 'Untitled'} ({it.get('source_type')})"
if it.get("published_at"):
    row += f" — {it['published_at'][:10]}"
if tags:
    row += f" — tags: {tags}"
```

### 1c. `search_library` — the only real gap
`RetrievedChunk` doesn't carry the date because the retriever SQL doesn't select
it. Three small edits in `retriever.py`:

1. Add `published_at: str | None = None` to the `RetrievedChunk` dataclass
   (`retriever.py:34`).
2. Add `ki.published_at` to the `SELECT` (`retriever.py:89`) and unpack it in the
   row loop (`retriever.py:107`), formatting to `YYYY-MM-DD`.
3. In `_format_chunks` (`agent.py:246`) append the date to each result head:
   `head += f" · {c.published_at}"` when present.

### 1d. Coverage signal for `search_library`
`browse_library` already reports a total; `search_library` should too. The
retriever over-fetches `top_k*5` candidates then trims — return the pre-trim
candidate count so `_format_chunks` can prepend a header:

```
12 matches; showing top 8:
```

Honest-signal note: that candidate count is capped at `top_k*5`. If a true
library-wide total is wanted, add a lightweight `SELECT count(*)` over the same
`MATCH` filter. Recommend starting with the candidate count (no extra query) and
revisiting if the exact total is ever needed.

### 1e. (Optional) date filter / sort on `search_library`
Add `since: str | None = None` (ISO date) and/or `sort: "relevance"|"newest"` args
so the agent can ask for "post-3.5" recency. Filter in the retriever SQL
(`AND ki.published_at >= :since`). Defer if 1a–1d already satisfy the recency need.

**Tests:** extend `tests/backend` chat-tool tests to assert dates + the coverage
header appear in tool output.

---

## Fix 2 — Transcript paging on `get_item`

`get_item` truncates at `_TRANSCRIPT_EXCERPT_CHARS = 3000` with no continuation
(`agent.py:271-273`). Add an offset window.

```python
@agent.tool
def get_item(ctx, item_id: str, transcript_offset: int = 0) -> str:
    ...
    return _format_item(item, offset=transcript_offset)
```

`_format_item` paginates the transcript and tells the agent how to continue:

```python
start = offset
end = offset + _TRANSCRIPT_EXCERPT_CHARS
window = transcript[start:end]
if start > 0:
    window = "…[continued]\n" + window
if end < len(transcript):
    window += (
        f"\n…[{len(transcript) - end} chars remain — "
        f"call get_item(item_id, transcript_offset={end}) to continue]"
    )
```

- Keep the per-call cap so a single tool result never floods context; the agent
  pages deliberately when it needs the rest.
- Update the docstring so the agent knows the offset exists and when to use it.
- **Tests:** assert offset slices correctly and the "remain / continue" hint
  appears only when there's more.

---

## Fix 3 — Vector search (hybrid + RRF), provider-agnostic scaffolding

Goal: land the full hybrid pipeline + RRF fusion + storage wiring **without
committing to an embedding provider**. Plugging a provider later is a one-class
change.

### 3a. Swappable embedder interface
New `merlin/rag/embeddings.py`:

```python
class Embedder(Protocol):
    dim: int
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class NullEmbedder:
    """Placeholder until a provider is chosen. Returns no vectors, so the
    hybrid retriever degrades to pure-FTS5 (today's behaviour)."""
    dim = 0
    def embed(self, texts): return []
```

`settings` gets `EMBEDDING_PROVIDER` (default `"none"` → `NullEmbedder`). Real
providers (OpenAI `text-embedding-3-*`, Voyage, local bge, etc.) are **left
unimplemented** — a `# TODO: choose provider` stub each. **Do not add API keys or
network calls yet.**

### 3b. Storage
The `embeddings` table already exists (reserved, unused). Confirm/define its shape:
`(knowledge_item_id, chunk_index, vector BLOB, dim, model)`. SQLite has no native
vector index — for the current corpus size a brute-force cosine over loaded
vectors is fine; note `sqlite-vec` as the scale-up option. No migration runs until
a real embedder exists, so this stays inert behind `NullEmbedder`.

### 3c. Retriever: add vector arm + RRF fusion
In `HybridRetriever.retrieve`:

```python
fts_hits = self._fts(session, query, ...)          # existing path, returns ranked list
vec_hits = self._vector(session, query, ...)        # [] when embedder is NullEmbedder
fused = self._rrf(fts_hits, vec_hits, k=60)[:top_k] # rank-based fusion
```

- `_rrf` merges by `knowledge_item_id`, scoring `Σ 1/(60 + rank)` across both
  lists; dedups items that appear in both.
- When `vec_hits == []` (no provider), `fused` == today's FTS5 ranking → **zero
  behaviour change until a provider is wired.** This is the safety property that
  lets us ship the scaffolding now.
- Update the module docstring (`retriever.py:11`) from "Phase 3 will add…" to "FTS5
  + vector via RRF (vector arm inert until an embedder is configured)."

### 3d. Backfill + ingest hook (stub)
- A `scripts/` backfill that embeds existing items — **written but a no-op under
  `NullEmbedder`.**
- An ingest-time hook to embed new items on `persist_result` — same, inert until a
  provider exists.

### 3e. Tests
- `_rrf` fusion ordering/dedup with synthetic ranked lists (no embedder needed —
  pure function).
- Retriever returns identical results to today when the embedder is `NullEmbedder`
  (the regression guard).

**Open decision (user):** which embedding provider — hosted (OpenAI/Voyage, best
quality, per-call cost, data leaves machine) vs local (bge/e5 via
`sentence-transformers`, free, private, heavier install). The interface in 3a makes
this swap a single class; everything else can land first.

---

## Suggested sequencing

1. **Fix 1a–1d** (+ optional 1e) — one PR, pure formatting + one SQL column. Ships
   the biggest perceived win (dates + coverage) immediately.
2. **Fix 2** — small, independent PR.
3. **Prompt nudge for parallel search** — one-line system-prompt change, ride
   along with #1 or #2.
4. **Fix 3 scaffolding** — separate PR; lands the hybrid+RRF machinery inert.
5. **Wire a real embedder** — only after the provider decision; flips `vec_hits`
   from `[]` to real and runs the backfill.
