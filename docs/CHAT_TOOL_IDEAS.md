# Chat agent tool ideas — backlog

Candidate enhancements to the agentic-chat tools in `merlin/rag/agent.py`. These
two are the generic, lower-effort wins worth keeping (others discussed — a
domain-specific comparator, stat-extraction, auto-tagging taxonomy — were
deferred or dropped because they couple the core to one use case or duplicate
what the agent already does by searching + reasoning).

Both build on infrastructure that already exists, so neither needs a schema
migration.

---

## 1. Date filtering in `search_library`

**What:** let the agent restrict results by publication date, so fast-moving
topics surface recent content and stale items drop out.

**Why:** `published_at` is already retrieved and shown on every result
(`RetrievedChunk.published_at`, surfaced in `_format_chunks`), but the agent can
only *react* to dates after the fact — it can't ask for "only content newer than
X". A hard filter stops old items from consuming result slots.

**Proposed tool signature** (add one param; keep it generic, not unit-specific):

```python
search_library(query, source_types=None, tags=None, limit=8, published_after=None)
# published_after: ISO date string "YYYY-MM-DD"; results older than this are excluded.
```

`published_after` is the flexible primitive; the agent can compute it from
relative asks ("last 6 months") itself. (A `published_before` could follow if a
windowed range is ever needed.)

**Implementation notes (the real cost — medium, not trivial):**

- The filter must be pushed into **both retriever arms**, not just the tool:
  - `HybridRetriever._fts` (`merlin/rag/retriever.py`) — add an
    `AND ki.published_at >= :published_after` clause to the SQL (alongside the
    existing `status` / `source_type` clauses).
  - `HybridRetriever._vector` — apply the same date predicate when selecting the
    candidate rows whose vectors are scored.
  - `HybridRetriever.count` — mirror the clause so the reported match total stays
    consistent with the filtered results.
- Thread a `published_after: str | None` param through `retrieve()` and `count()`.
- `published_at` can be NULL (not all sources carry a date) — decide whether a
  date filter should **exclude** undated items (stricter, recommended) or keep
  them. Be explicit; document it in the docstring.
- Update the `search_library` docstring so the model knows the param exists and
  what NULL-date behaviour to expect.

**Effort:** medium. Touches two arms + count + the service tool. No migration.

---

## 2. `get_similar` — "more like this item"

**What:** a new tool that, given an `item_id`, returns other items closest to it
in meaning — a "related content / people who liked this also liked…" primitive
for discovery.

**Why:** when the agent (or user) lands on a strong source, the natural next move
is "what else is like this?". Keyword search can't express that well; vector
similarity can.

**Proposed tool signature:**

```python
get_similar(item_id, limit=8) -> str
# Returns id + title + source + date for the most semantically-similar items,
# excluding item_id itself. Falls back gracefully when no embeddings exist.
```

**Implementation notes (cheaper than it looks — the infra is already there):**

- The `embeddings` table already stores one vector per item (chunk_index=0), and
  `HybridRetriever._vector` already does **brute-force cosine in Python** over
  those vectors. `get_similar` is the same machinery with a stored item vector as
  the query instead of a freshly-embedded query string:
  1. Load the target item's vector from `embeddings` (by `knowledge_item_id`).
  2. Cosine it against all other item vectors (reuse the existing `_cosine` helper).
  3. Return the top-N, excluding the target, formatted like `_format_browse` /
     `_format_chunks`.
- **No live embedding call needed** — the query vector is already precomputed and
  stored, so this is pure local compute (unlike `search_library`, which embeds
  the query live).
- Degrade gracefully: if `EMBEDDING_PROVIDER=none`, the target has no vector, or
  the store is empty, return an informative string (the agent's tools never
  crash the run — same contract as the existing tools).
- Register as a new `@agent.tool` and mention it in `AGENT_SYSTEM_PROMPT`
  (e.g. step 3, "go deep / find related").

**Effort:** low. Reuses `_cosine` + the `embeddings` table; no new dependency,
no migration, no live API call.

---

## Out of scope (recorded so we don't re-litigate)

- **Domain comparator** (`compare_classes(...)`) and **stat extraction**
  (`show_stats`) — bake one use case (e.g. a specific game) into the general KM
  core; the agent already synthesises comparisons and pulls figures by reading
  sources.
- **Boolean AND search** (`match_mode="all"`) — only cleanly applies to the FTS
  arm; the vector arm has no boolean semantics and the rerank pass already does
  the "must be about both" precision work.
- **Auto namespaced tags at ingest** (`version:3.6`, `class:Cra`) — sound idea,
  but a separate ingest-pipeline project with controlled-vocabulary drift risk.
- **`assess_coverage`** — largely duplicates what the agent does by noticing thin
  results; more useful as a user-facing library-gaps view than an agent tool.
