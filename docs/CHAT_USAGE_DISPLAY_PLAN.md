# Plan — Live token / cost / context-window display in chat

> Status: **SHIPPED.** Per-turn tokens, estimated cost, and context-window
> occupancy now stream under each answer (`data-usage` part → `UsageFooter`) with
> a running `ContextMeter` by the composer, on both the library and Reader chats.
> Builds on the shipped cost-tracking feature (`docs/COST_AND_TOKEN_TRACKING.md`
> + the `llm_usage` table), which made spend visible in Insights after the fact.
>
> **Deviations from the draft below (simpler than planned), because the chat
> model is pinned to one provider via an OpenRouter preset (DeepSeek-only):**
> - **No `/models` catalog service (§4 dropped).** The context window is a known
>   constant — `settings.chat_context_window` (default `1_048_576`, DeepSeek's
>   1.05M window) — and the prices are fixed, so nothing is fetched at runtime.
> - **Cost reuses `merlin/llm_pricing.py`, made cache-aware.** Rates corrected to
>   the pinned DeepSeek provider (`in 0.14 / out 0.28 / cache_read 0.0028`); cached
>   input is billed at the discounted rate (a multi-turn thread is mostly cache
>   hits, so the naive all-at-`in` number overstated cost several-fold). Pricing
>   resolves the response's *resolved* model name (the configured `@preset/…`
>   never matched a map key, so the estimate had been silently NULL).
> - **Context occupancy = the *last* request's prompt + answer**, not a per-turn
>   peak and not the summed `RunUsage` (which multiplies the window by the tool
>   loop). It already includes the whole re-sent conversation, so it climbs turn
>   over turn — the "am I filling the window?" signal. See `_turn_usage` /
>   `_last_response_usage` in `api/routers/chat.py`.
> - The authoritative `/generation` cost lookup is **unchanged** — it still
>   reconciles into `llm_usage` for Insights; the in-chat number is the live
>   cache-aware estimate.
>
> The original draft follows for context.

## 1. Goal

After every chat turn, show under the assistant message:

- **tokens** this turn used (in / out),
- **cost** of this turn (USD), and
- **context window** used — `input_tokens / model_context_length` as a number +
  a small bar (e.g. "47k / 1.0M · 4%").

And, near the composer, a **running context-window meter** for the conversation
(driven by the latest turn's prompt size), so you can see when a long thread is
filling the window. Visibility only — nothing truncates or blocks.

## 2. What we already have (reuse, don't rebuild)

- Usage accounting is enabled on the chat model (`merlin/rag/model.py`,
  `extra_body={"usage":{"include":true}}`).
- Chat `on_complete` already runs for both paths and **already emits custom
  data-parts** (`data-citations`, `data-sources-viewed`) that the frontend
  renders and persists in the thread. We add one more: **`data-usage`**.
- A background task already records the authoritative cost to `llm_usage` via the
  OpenRouter `/generation` endpoint. That stays — it's the source of truth for
  **Insights**. The in-chat number is a **live estimate** (the real cost lags
  ~12s; we don't make the UI wait).

## 3. The three numbers — where each comes from

| Number | Source | Notes |
|---|---|---|
| **tokens in/out (turn)** | `RunUsage` (`result.usage`) | Summed across the tool loop — the right "what did this turn cost in tokens" number. |
| **cost (turn, live)** | computed = `in × price_prompt + out × price_completion` | Prices from the OpenRouter **/models** catalog (§4). Instant, no extra call. Authoritative cost still reconciled into `llm_usage` in the background. |
| **context used** | **peak per-request** `input_tokens` = `max(m.usage.input_tokens for m in result.all_messages() if response)` | NOT `RunUsage.input_tokens` (that's the *sum* across requests). The last/biggest request's prompt = how full the window actually got. |
| **context limit** | `/models[resolved_model].context_length` | Falls back to `settings.chat_context_window` then a safe default. |

**Verified:** per-`ModelResponse` usage is populated; `/models` returns
`context_length` (1,048,576 for deepseek-v4-flash) and `pricing.prompt` /
`pricing.completion` (per-token USD).

## 4. New backend piece — OpenRouter model catalog

`merlin/services/openrouter_catalog.py`:

```python
def get_model_info(model: str) -> dict | None:
    # {"context_length": int, "price_prompt": float, "price_completion": float}
    # Cached (module-level, TTL ~6h). Lazy: first call fetches GET /models.
    # Best-effort: returns None on failure (caller degrades gracefully).
```

- One GET to `{openrouter_endpoint}/models`, parsed into a `{id: info}` dict,
  cached with a timestamp (no `Date.now()` in core is fine here — this is a
  service, not a workflow script; use `time.monotonic()`).
- **Preset resolution:** our configured id is `@preset/…`, absent from `/models`.
  Look up by the **resolved** model name the response reports
  (`ModelResponse.model_name`, e.g. `deepseek/deepseek-v4-flash-20260423`), then
  by a prefix match (`deepseek/deepseek-v4-flash*`), then `settings.chat_model_name`.
- Config fallback: `settings.chat_context_window: int = 0` (0 ⇒ unknown → UI
  shows tokens without a %). Optional `CHAT_CONTEXT_WINDOW` override.

## 5. Backend — assemble + emit `data-usage`

In `api/routers/chat.py`, extend the existing `on_complete` (the `_make_on_complete`
factory, which already yields data-parts):

```python
async def on_complete(result):
    _queue_chat_usage(background_tasks, result, item_id=item_id)  # existing (Insights)
    yield DataChunk(type="data-usage", data=_turn_usage(result))   # NEW (live UI)
    ...                                                            # existing citations
```

`_turn_usage(result)` (new helper):

```python
{
  "input_tokens": u.input_tokens,
  "output_tokens": u.output_tokens,
  "requests": u.requests,
  "cost_usd": est_cost,            # from catalog prices; None if unknown
  "cost_estimated": True,          # flag so UI can show "~$"
  "context_used": peak_input,      # max per-request input_tokens
  "context_limit": ctx_limit,      # from catalog/config; None if unknown
}
```

- Works for **both** paths — the item (Reader) path already has an `on_complete`
  now; it just had no citations. It gets `data-usage` too.
- Also stash `context_used`/`context_limit` into the existing `llm_usage.meta`
  (one line in `record_chat_turn`) so Insights *could* later chart context
  utilization. No new column.

## 6. Frontend

### 6a. Type + render the part (`web/src/components/chat/Message.tsx`)
- The streamed `message.parts` already includes our data-parts; add a
  `data-usage` case. Render a compact **footer** under the answer:
  `↑12.3k ↓1.2k · ~$0.0004 · ctx 47k/1.0M (4%)` with a thin progress bar for the
  context %. Tooltip spells out requests + exact tokens.
- Define the part shape in the chat types (the chat path is decoupled from the
  generated OpenAPI client — types live with `useAgentChat.ts`).

### 6b. Composer context meter (library chat + Reader)
- Read the **most recent** `data-usage` part in the message list → small meter by
  the input: "Context 47k / 1.0M". Colour shifts amber > 75%, red > 90%.
- `chat.tsx` (library) and `components/chat/ItemChat.tsx` (Reader) share it via a
  tiny `ContextMeter` component fed from the messages.

### 6c. Persistence
- Free: `data-usage` rides in the assistant message `parts`, which the client
  already PUTs to `/api/chat/threads/{id}`. A reopened thread re-renders the
  footers and restores the composer meter. Reader chat stays ephemeral (no
  threads) — fine, it shows live only.

## 7. Edge cases

- **Cost is an estimate** (`cost_estimated: true`) — the live number uses catalog
  list prices; the authoritative `/generation` cost still lands in `llm_usage`
  for Insights. Show `~$` to signal "estimate". (If list price == actual, drop
  the tilde later.)
- **Unknown context limit** (preset unresolved, catalog fetch failed) → show
  tokens, hide the `%`/bar. Never show a fake denominator.
- **Tool loop inflates a turn's tokens** — that's correct; the footer is
  per-*turn* (the loop is one turn). The context meter uses peak single-request
  input, so it reflects the real window pressure, not the summed billing.
- **No network in tests** — catalog service returns None; `_turn_usage` degrades
  to tokens-only; assertions target the `data-usage` part's presence + token
  fields, not cost/context.

## 8. Tests (`tests/backend/test_chat.py` + `test_usage.py`)
- A scripted `FunctionModel` run through `/api/chat` emits a `data-usage` part
  with `input_tokens`/`output_tokens` present (assert on the SSE objects, like the
  existing citation tests).
- Item-path chat also emits `data-usage`.
- `openrouter_catalog.get_model_info`: monkeypatch the HTTP GET → assert prefix
  resolution + cost math; assert None-degradation on failure.
- `_turn_usage` peak-context math: a fake result with two responses (inputs 10k,
  47k) → `context_used == 47k`, not 57k.

## 9. Effort
**Small–medium.** One new cached catalog service, one new data-part + helper
(reusing the existing `on_complete`/DataChunk plumbing), and a footer + meter on
the frontend. No migration, no new endpoint. The live cost is the only subtlety
(estimate now, authoritative in Insights) and it's already half-solved.
```
