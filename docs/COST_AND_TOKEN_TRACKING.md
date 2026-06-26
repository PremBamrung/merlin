# Plan — Cost & token tracking (visibility, no capping)

> Status: **DECIDED, ready to build.** Locked: tracking is for **visibility only**
> — record tokens/cost and surface them; **no budgets or hard caps**. Capture all
> three LLM/AI surfaces, phased with **chat first**. The existing
> `UsageLimits(request_limit=…)` loop guard stays as-is (it's a safety guard, not a
> budget).

## 1. Decision

Persist every LLM/transcription call's usage to one `llm_usage` table, attribute it
to a surface + model (+ item where relevant), compute cost (OpenRouter's actual
cost when available, a small pricing map otherwise), and show it in Insights.
Nothing blocks or rejects on spend.

## 2. Current state (what changes)

Nothing is tracked. Only `UsageLimits(request_limit=…)` in `api/routers/chat.py`
caps **round-trips** (not tokens/$). `ingest` stores `item.llm_model` but no token
counts. We add capture + a table + reads; we do **not** add any enforcement.

## 3. The three spend sites + their usage data

| Surface | Where | Usage available | Billing unit |
|---|---|---|---|
| **chat** | `api/routers/chat.py` `on_complete(result)` | `result.usage()` → `RunUsage(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, requests, tool_calls)` | tokens |
| **summarize** | `merlin/knowledge_sources/plugins/youtube/summarizer.py:338` (`invoke`), `:428` (`stream`) | `AIMessage.usage_metadata` `{input_tokens, output_tokens, total_tokens}` per call; **sum across chunks** | tokens |
| **transcribe** | `merlin/knowledge_sources/plugins/youtube/audio_transcriber.py` | response `duration` (audio seconds); already read | audio seconds |

`on_complete` already receives the `AgentRunResult` (same hook the citations use),
so chat capture is a few lines. For ingest, the summariser/transcriber are **core**
(must not touch the DB — dependency arrow), so they **return** usage numbers up
through `IngestResult`, and `services/ingest.persist_result` writes the rows.

## 4. Storage — migration `005`

```
llm_usage
  id                TEXT PK
  created_at        DATETIME (UTC)
  surface           TEXT   -- 'chat' | 'summarize' | 'transcribe'
  provider          TEXT   -- 'openrouter' | 'azure' | 'groq'
  model             TEXT
  input_tokens      INTEGER NULL
  output_tokens     INTEGER NULL
  audio_seconds     REAL    NULL
  requests          INTEGER DEFAULT 1   -- model round-trips (chat tool loop)
  cost_usd          REAL    NULL        -- actual (OpenRouter) or computed
  knowledge_item_id TEXT NULL  FK -> knowledge_items(id) ON DELETE SET NULL
  meta              TEXT NULL           -- JSON: cache tokens, tool_calls, thread_id…
```

Plain `op.create_table` migration, `down_revision = '004'` (latest is
`004_add_youtube_description`; if persistence's migration lands first, renumber).
No FTS/triggers, so **autogenerate is acceptable** here (unlike the FTS migration).
Add the SQLAlchemy `LlmUsage` model to `merlin/db/models.py`.

## 5. Build steps

### Phase 0 — table + service
- Migration `005` + `LlmUsage` model.
- `merlin/services/usage.py`:
  ```python
  def record(*, surface, provider, model, input_tokens=None, output_tokens=None,
             audio_seconds=None, requests=1, cost_usd=None,
             knowledge_item_id=None, meta=None) -> None
  def spend_by_day() -> list[dict]
  def spend_by_surface() -> list[dict]
  def spend_by_model() -> list[dict]
  def total_spend() -> dict      # {tokens_in, tokens_out, cost_usd}
  def cost_for_item(item_id) -> float | None
  ```
  Returns plain dicts; opens a short-lived session via `get_db()`/`SessionFactory`.

### Phase 1 — chat capture (highest value, smallest)
In `api/routers/chat.py`, extend the `on_complete(result)` hook (it already runs
for the library-wide path; add it to the item path too if you want Reader chat
costed):
```python
u = result.usage()
usage_service.record(
    surface="chat", provider="openrouter", model=settings.chat_model_name,
    input_tokens=u.input_tokens, output_tokens=u.output_tokens,
    requests=u.requests, cost_usd=_cost("openrouter", settings.chat_model_name, u),
    meta={"cache_read": u.cache_read_tokens, "tool_calls": u.tool_calls},
)
```
Optionally also stream a `data-usage` part so the UI can show "this turn used N
tokens (~$X)" under the answer.

### Phase 2 — ingest capture
- `summarizer.py`: accumulate `usage_metadata` across every `invoke`/`stream` call
  (sum input/output); for `.stream()`, read `usage_metadata` off the **final**
  aggregated chunk. Add token totals to the returned summary result.
- `audio_transcriber.py`: sum chunk `duration`s; return the total.
- `IngestResult` (`knowledge_sources/base.py`): add
  `summarize_input_tokens/output_tokens` and `transcribe_audio_seconds` (+ model).
- `services/ingest.persist_result`: write a `summarize` row and a `transcribe` row
  (`knowledge_item_id` set) after the item is saved.

### Phase 3 — cost
`merlin/llm_pricing.py`:
```python
PRICING = {  # USD per 1M tokens; as-of 2026-06
  "deepseek/deepseek-v4-flash": {"in": …, "out": …},
  # …azure models…
}
GROQ_AUDIO_PER_HOUR = …
def cost(provider, model, *, input_tokens=0, output_tokens=0, audio_seconds=0): ...
```
Prefer **OpenRouter's actual cost**: enable it on the chat model
(`extra_body={"usage": {"include": true}}` / OpenRouter `/generation` endpoint) and
store that as `cost_usd`; use `PRICING` only for Azure and as a fallback. Stamp the
map with an as-of date; it *will* go stale.

### Phase 4 — Insights surface
- `GET /api/insights/usage` (wrap `usage.*` aggregates), per the existing insights
  router pattern.
- A Recharts card on the Insights page: daily spend, stacked by surface (and/or by
  model). Optional: a per-item cost line in the Reader (`cost_for_item`).

## 6. Test plan (`tests/backend/`)
- `usage.record` writes a row; aggregates sum correctly (temp DB).
- **Chat**: scripted `FunctionModel` run through `/api/chat`; assert one `llm_usage`
  row with `surface='chat'`, `requests>=1`, token counts > 0. (FunctionModel
  reports usage; assert the row exists and fields populate.)
- **Cost**: `llm_pricing.cost` math for a known model; OpenRouter passthrough
  preferred-over-map precedence.
- **Ingest**: monkeypatch the summariser/transcriber to return known token/seconds
  totals; assert `persist_result` writes a `summarize` + `transcribe` row tied to
  the item.

## 7. Acceptance criteria
- After a chat turn, a row appears with tokens + `requests` + a cost (actual or
  computed).
- After an ingest, summarize + transcribe rows appear, attributable to the item.
- Insights shows daily/total spend split by surface and model.
- **No** code path rejects or throttles based on spend (visibility only).

## 8. Gotchas
- **Streaming usage timing:** LangChain `usage_metadata` is on the **final** stream
  chunk — accumulate, don't read mid-stream. Pydantic AI: call `result.usage()`
  **after** the stream (in `on_complete`).
- **Chat tool loop = multiple requests:** `RunUsage.requests` can be >1; tokens are
  already summed across the loop — record `requests` so a runaway turn is visible.
- **Azure has no cost passthrough** → needs `PRICING`. OpenRouter returns actual
  cost. Support both since `llm_provider` can be either.
- **Dependency arrow:** summariser/transcriber (core) must **return** numbers, not
  write rows; persistence lives in `services/ingest`.
- **Backfill:** old items have no rows — Insights treats missing as "unknown," not
  "$0."
- **Cache tokens** priced differently per provider; stash in `meta`, refine later.

## 9. Effort
**Medium.** Migration + thin usage service + 1 trivial seam (chat) + 1 threaded
seam (ingest) + a pricing map + one Insights chart. Phase 1 alone (chat tokens) is
~half a day and answers the recurring-cost question.
