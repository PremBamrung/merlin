# Agentic Chat Rebuild — Plan (Pydantic AI + Vercel AI SDK)

> Status: **SHIPPED (2026-06-19).** Implemented across all phases. Backend:
> `merlin/rag/{model,agent}.py` + rewritten `retriever.py`, `services/chat.py`,
> and the `VercelAIAdapter`-based `api/routers/chat.py`. Frontend: `useChat` via
> `web/src/hooks/useAgentChat.ts`, parts-rendering `Message.tsx`, and the
> migrated `ItemChat.tsx` (the old `useChatStream`/custom SSE consumer removed).
> Verified live against OpenRouter (`deepseek/deepseek-v4-flash`, a reasoning
> model) end-to-end through the HTTP route; 118 backend tests pass; frontend
> typechecks/builds/lints clean with the AI SDK isolated to a lazy chunk.
> **Deferred (not a chat prerequisite):** Phase 6, the app-wide Azure→OpenRouter
> migration — `llm_provider` is still `azure`-capable in `config.py`.
> The text below is the design reference it was built from.
>
> Stack decision (locked): **backend = Pydantic AI** agent + tools; **frontend =
> Vercel AI SDK** (`ai` + `@ai-sdk/react`) consuming Pydantic AI's
> `VercelAIAdapter` SSE stream. The chat path becomes **async** (Pydantic AI
> streaming is async-only); the rest of the app stays sync. An earlier
> raw-`openai`-SDK design was considered and dropped — see §10 for why.
>
> **Inputs resolved (2026-06-19):**
> - **Reader single-item chat** → `ItemChat.tsx` **migrates to `useChat`**; it
>   passes `item_id` in `body.filters`, and `/api/chat` routes that to the sync
>   single-item path **but emits the same Vercel stream**. One endpoint, one
>   client transport. (Resolves the old contradiction — see §3a + §9.)
> - **Azure→OpenRouter migration** → **decoupled; chat ships first.** The agent
>   uses its own OpenRouter `model.py`, so the app-wide Azure removal is a
>   *separate, later* gated unit — **not** a prerequisite. (See §8 + §9.)
> - **Chat model** → a **reasoning model** on OpenRouter, so `useChat` renders
>   real `reasoning` parts (not just the tool trace). (See §6b + §9.)
>
> **Build gate — PASSED (2026-06-19).** Verified against pinned versions:
> `pydantic-ai==1.107.0`, `ai@^6.0.208`, `@ai-sdk/react@^3.0.210` (AI SDK **v6**,
> newer than the v5 the plan first assumed → set adapter `sdk_version=6`).
> Confirmed end-to-end with `TestModel`:
> - `Agent(...)` builds **model-less**; the model is passed at run time
>   (`dispatch_request(model=...)`/`run_stream(model=...)`) → fully lazy
>   construction, no import-time key, `TestModel` injectable in tests. ✓
> - `VercelAIAdapter.dispatch_request(request, *, agent, deps, model,
>   instructions, usage_limits, on_complete, sdk_version=6) -> Response` does the
>   whole build-run-encode internally — simpler than the 3-step form the plan
>   sketched. ✓
> - The request model is `extra='allow'` (camelCase aliases), so our extra
>   `filters` field rides in the same JSON body as `messages`. ✓
> - Tool calls stream as `tool-input-*` / `tool-output-available` parts; server
>   tools reach the client as **`dynamic-tool`** parts (`toolName`, `toolCallId`,
>   `state`, `input`, `output`). Citation accumulation via `deps` works. ✓
> - Client: `useChat` + `DefaultChatTransport({ api })`; per-send filters via
>   `sendMessage(msg, { body: { filters } })` (`ChatRequestOptions.body`). ✓

## 1. Why

Today's chat is a **one-shot RAG**: it wraps the *entire* user question in
double quotes and runs it as a single FTS5 phrase query
(`merlin/rag/retriever.py::_escape_fts`). Almost no natural-language question
appears verbatim in the indexed text, so retrieval usually returns **zero**
rows → empty context → the system prompt invites the model to answer from
general knowledge. It looks like a chatbot that has no idea what's in the
library. Secondary issues: ≤5 items × `summary[:500]` of context, no multi-turn
retrieval, transcripts indexed but never quoted back, keyword-only.

The chat is currently unused, so we rebuild it **greenfield** — no migration
constraints on the existing chat UI.

## 2. Goal

An **agentic tool-calling chat**: the LLM decides what to search/fetch, can
iterate and refine, and grounds answers in what it actually retrieved — with a
rich UI that shows the **reasoning, tool calls, their parameters, and results**
inline, streamed. Extensible: web search and per-source tools (Reddit, YouTube
comments, articles, Karpathy concept pages) slot in by registering one more
`@agent.tool`. Investigation only — chat reads the DB, never writes.

### Why this stack
- The hard part of a "show-the-reasoning" chat is the **frontend**: a streaming
  message-parts protocol + UI state machine (interleaved text / tool-invocation
  / reasoning parts, partial tool args, ordering). The **Vercel AI SDK's
  `useChat` renders those parts out of the box**, and **Pydantic AI's
  `VercelAIAdapter` emits exactly that protocol** — the two halves snap together.
- Pydantic AI's surface we touch is small and flat (`Agent`, `@agent.tool`,
  `RunContext` deps, `run_stream_events`); we never touch its graph internals
  (`agent.iter`/nodes). That keeps us out of the LangChain-style "framework
  jungle."
- Sync tool functions are auto-offloaded to a threadpool by Pydantic AI, so our
  **synchronous SQLite/SQLAlchemy tools work unchanged**.

## 3. Architecture

Dependency arrow preserved: `api/` → `merlin.services.chat` →
`merlin.rag.{agent, tools, retriever, model}` → `merlin.services.library` / DB.
`merlin/` may import `pydantic_ai` (it already imports `langchain_openai` in
`config.py`); it still must **not** import `fastapi`/`streamlit`/`api`. The
`VercelAIAdapter` glue lives in `api/`, not `merlin/`.

**Async scope:** only `services/chat.answer*` and the `/api/chat` route become
async. The summariser, ingest pipeline, and all other services stay sync.
`get_db()` stays a sync context manager — used inside sync tool functions, which
Pydantic AI runs in a threadpool.

**Auth/middleware (verified in `api/main.py`):** the API has **no auth layer** —
only `CORSMiddleware` (pure ASGI). `app_password` is not enforced here, so
`/api/chat` is open like every other endpoint (no auth work for the Vercel SDK).
Because the only middleware is pure-ASGI CORS, the `http.disconnect` /
`BaseHTTPMiddleware` footgun (§7.2) does **not** apply today — re-check only if a
`BaseHTTPMiddleware` is ever added. ⚠️ Note this now makes `/api/chat` a
**metered, abusable surface** — each request spends OpenRouter tokens through an
agent loop (up to `chat_max_requests` model calls). Acceptable for a personal
app; revisit if ever exposed publicly.

### 3a. The Reader single-item path (`item_id`) — one endpoint, two behaviours

`/api/chat` handles **both** the library-wide agent run and the Reader's
single-item chat, distinguished by `item_id` in the request's `filters`:

- **No `item_id`** → full Pydantic AI agent run (tools, iteration) via the adapter.
- **`item_id` set** → the **sync single-item answer** (`chat.answer` with the
  full transcript, behaviour unchanged) — but its token stream is **wrapped into
  the same Vercel stream** the adapter emits, so the client speaks one protocol.

This is the wrinkle to get right: the adapter is built around an `agent.run`, but
the single-item path is a plain token generator. Implementation options to settle
during Phase 3 (pick the simplest the pinned adapter allows):
  (a) feed the single-item turn through the *same* agent with a `system_prompt`
  override + tools disabled, so it flows through the adapter unchanged (preferred
  if the pinned API supports per-run system prompt + empty toolset); or
  (b) hand-emit the minimal Vercel `text`-part frames for the single-item path
  without the adapter, reusing the adapter's wire format.
Either way the client is **pure `useChat`** — `ItemChat.tsx` migrates off the
deleted custom SSE consumer (§9, resolved).

### New / changed modules

| File | Change |
|---|---|
| `merlin/config.py` | **+** `chat_model: str = ""` (optional OpenRouter model override — **falls back to the existing `openrouter_model_deployment`** already in `.env`, so no new required config) and `chat_max_requests: int = 8` (agent loop cap). Reuses the existing `openrouter_api_key` / `openrouter_endpoint`. (No `chat_agentic` flag — Pydantic AI always tool-calls.) The chosen model **must support tool-calling**; set `chat_model` if the summariser's model isn't ideal for it. |
| `merlin/rag/model.py` | **new** — `build_chat_model()` returns a Pydantic AI model pointed at **OpenRouter** (OpenAI-compatible): `OpenAIChatModel(settings.chat_model, provider=OpenRouterProvider(api_key=settings.openrouter_api_key))`. Chat-only; the summariser keeps `settings.llm` untouched. (Azure is **not** used for chat — see §6b.) |
| `merlin/rag/retriever.py` | **rewrite** — replace the whole-question phrase query with tokenized OR-of-prefixes + `bm25` ranking + real `snippet()` excerpts. Engine behind the `search_library` tool. Keep `RetrievedChunk`. |
| `merlin/rag/agent.py` | **new** — the module-level `Agent` (`deps_type=ChatDeps`, `system_prompt=AGENT_SYSTEM_PROMPT`, model built lazily) + the `@agent.tool` functions. `ChatDeps` carries the chat-level filters + a citation accumulator. |
| `merlin/rag/prompts.py` | **+** `AGENT_SYSTEM_PROMPT`. Keep `ITEM_CHAT_SYSTEM_PROMPT` (Reader single-item, unchanged). `MERLIN_SYSTEM_PROMPT`/`format_context` become dead once the one-shot path is gone — remove or keep for reference. |
| `merlin/services/chat.py` | **rewrite** — `item_id` (Reader) path stays as a sync single-item call (unchanged behaviour), but its output is wrapped into the Vercel stream by the route (§3a). The library-wide path becomes the Pydantic AI agent run, exposed for the adapter. |
| `api/routers/chat.py` | **rewrite** — `async def chat(request)` using the `VercelAIAdapter` 3-step pattern (`build_run_input` → `run_stream` → `encode_stream`) so we can read `filters` from the request body, build `ChatDeps`, and set a `request_limit`. Set no-buffer streaming headers. |
| `api/sse.py` | chat SSE now comes from the adapter's `encode_stream`; the hand-rolled `chat_event_stream` is removed. The **task-progress** SSE stream stays as-is. |
| `api/schemas.py` | `ChatRequest`/`Citation` for the *custom* `/api/chat` body shape are replaced by the Vercel AI SDK message protocol; keep a small request model for our extra `filters` field. |
| `web` deps | **+** `ai`, `@ai-sdk/react` (chat route only; lazy-loaded). |
| `web/src/routes/chat.tsx` | **rewrite** — `useChat` against `/api/chat`, render `message.parts`. FilterBar stays (feeds `filters` into the request body). ⚠️ Use the **pinned AI SDK v5** signature: transport/body config moved off the v4 `useChat({api, body})` shape to `transport: new DefaultChatTransport({ api, body })` (verify exact form at impl time) — and confirm `filters` are re-sent on **every** send, not just hook init. |
| `web/src/components/chat/Message.tsx` | **rewrite** — render typed parts: `text`, `tool-invocation` (name + args + result → the tool-trace + citations), `reasoning`. |
| `web/src/components/chat/ItemChat.tsx` | **rewrite** — migrate off `useChatStream` to `useChat` against `/api/chat` with `item_id` in `body.filters` (§3a). Reader chat behaviour is preserved; only its transport changes. |
| `web/src/hooks/useChatStream.ts`, custom chat SSE consumer (`chatStream`) in `lib/api/client.ts` | **remove** (both the main chat route *and* `ItemChat` move to `useChat`). The task-progress SSE consumer stays. |
| `tests/backend/` | use Pydantic AI's `TestModel`/`FunctionModel` to script tool-call→answer with **no network**; assert tools run, citations accumulate, request_limit enforced. |

## 4. Tools (initial set — all wrap existing `merlin.services`, all sync)

```python
@dataclass
class ChatDeps:
    source_types: list[str] | None = None
    tags: list[str] | None = None
    cited: dict[str, dict] = field(default_factory=dict)  # item_id -> citation

# NOTE: do NOT call build_chat_model() at import time — that constructs the
# OpenRouter model (and needs a key) just to import the module, breaking test
# collection and violating config.py's deliberate lazy-LLM convention. Pass a
# deferred model reference (e.g. a string id the agent resolves lazily) or build
# the agent inside a cached factory. Sketch below assumes lazy construction.
agent = Agent(_deferred_chat_model(), deps_type=ChatDeps, system_prompt=AGENT_SYSTEM_PROMPT)

@agent.tool
def search_library(ctx: RunContext[ChatDeps], query: str,
                   source_types: list[str] | None = None,
                   tags: list[str] | None = None, limit: int = 8) -> str:
    with get_db() as db:                       # sync, runs in threadpool
        chunks = _retriever.retrieve(db, query,
                    source_types or ctx.deps.source_types,
                    tags or ctx.deps.tags, top_k=limit)
    for c in chunks:
        ctx.deps.cite(c)                        # accumulate for citations
    return _format_for_model(chunks)            # compact, capped text
```

| Tool | Wraps | Purpose |
|---|---|---|
| `search_library(query, source_types?, tags?, limit?)` | fixed retriever | keyword recall; the LLM crafts/refines queries |
| `get_item(item_id)` | `library.get_item` | summary + **transcript snippet** (capped) for depth |
| `browse_library(source_type?, tag?, sort?, limit?)` | `library.list_items` | filter / count / enumerate (non-search questions) |
| `list_tags()` | `library.list_tags` | vocabulary discovery |
| `list_source_types()` | `library.list_source_types` | what content exists |

Chat-level filters (FilterBar) arrive in `ChatDeps` and act as defaults a tool
can override. **Future tools** (`web_search`, per-source, concept-pages) = one
more `@agent.tool`; no other change.

## 5. Citations

Two complementary surfaces, no separate retrieval pass:
1. **The tool trace IS the citation surface** — `search_library` / `get_item`
   results are streamed as `tool-invocation` parts and rendered with item
   titles + links. The user sees what was actually used.
2. **Consolidated citations** — `ChatDeps.cited` accumulates touched items; emit
   them at the end as a Vercel AI SDK **data part** (or message annotation) for a
   tidy "Sources" list. Captured via the adapter's `on_complete` callback.

## 6. Streaming protocol & endpoint

`/api/chat` uses the adapter's explicit 3-step form (so we can inject deps from
the request body and cap the loop):

```python
@router.post("/chat")
async def chat(request: Request) -> Response:
    body = await request.body()
    run_input = VercelAIAdapter.build_run_input(body)
    filters = _extract_filters(request)                 # our extra body field
    adapter = VercelAIAdapter(agent=agent, run_input=run_input,
                              deps=ChatDeps(**filters))
    events = adapter.run_stream(usage_limits=UsageLimits(request_limit=settings.chat_max_requests))
    sse = adapter.encode_stream(events)
    return StreamingResponse(sse, media_type="text/event-stream",
                             headers=_sse_headers())     # see §7
```

The Vercel AI SDK on the client consumes this with `useChat`; it renders text,
tool calls (args + results), and reasoning parts, and handles framing,
done-signalling, abort, and efficient incremental rendering itself.

> Pydantic AI API names (`OpenAIChatModel`, `AzureProvider`,
> `OpenRouterProvider`, `VercelAIAdapter`, `UsageLimits`) move between versions —
> **pin `pydantic-ai`** and verify these against the pinned version at
> implementation time.

## 6b. Agent behaviour, errors, model, observability

- **System prompt is the main quality lever.** `AGENT_SYSTEM_PROMPT` must
  instruct the agent to: search the library before answering; prefer library
  content over general knowledge and *say so* when the library lacks the answer;
  iterate/refine searches when the first is thin; use `get_item` for depth; cite.
  Treat its wording as a real design + tuning task, not a stub.
- **Tool errors (decided, no input needed):** each tool catches its own
  exceptions and returns an informative string so the model can react; raise
  `ModelRetry` only for transient/recoverable cases. A tool never crashes the run.
- **Chat model — DECIDED (reasoning model).** Chat uses an **OpenAI-compatible
  provider (OpenRouter)** with a modern **reasoning + tool-calling** model, set
  via `settings.chat_model`, so the Vercel AI SDK renders real `reasoning` parts
  (not just the tool trace). Pick a specific reasoning model that **supports
  tool-calling** on OpenRouter at impl time and pin it. **Azure is dropped for
  chat** — but note (per §8/§9) this is fully self-contained in the chat
  `model.py`; the app-wide Azure removal is a *separate, later* unit. The code
  renders `reasoning` parts when present, so a non-reasoning fallback still works.
- **History (cap by turn, not raw count):** the Vercel AI SDK sends the full
  client-side message list each turn; the adapter replays it (incl. tool calls)
  as Pydantic AI history. **Cap its length to bound tokens — but truncate on
  complete conversation-turn boundaries, never mid-tool-exchange.** Slicing a raw
  message array can orphan a `tool-call` from its `tool-result`, violating the
  "one `tool` reply per `tool_call_id`" invariant the adapter relies on and
  breaking replay.
- **Observability:** log per run — tool name + args + latency, request count,
  token usage, `finish_reason` — to diagnose runaway loops and token growth.
- **Verify against pinned versions:** the consolidated-citations **data part**
  (§5) depends on Vercel AI SDK v5 data-part support + the Pydantic AI adapter
  emitting it. The **tool-trace-as-citations** path is guaranteed regardless; the
  consolidated "Sources" part is the bit to confirm at build time.

## 7. Footguns: what the framework handles vs. what's still on us

**Handled by Pydantic AI / Vercel AI SDK now (were manual in the raw plan):**
- Streaming tool-call **delta assembly by index** — Pydantic AI.
- Strict **one `tool` message per `tool_call_id`** protocol — Pydantic AI.
- **Sync tool blocking** — Pydantic AI threadpools sync tools.
- **SSE framing / done sentinel / incremental render / no-reconnect-on-POST /
  AbortError** — Vercel AI SDK + adapter. (No per-token `setState` storm.)
- **Loop cap / force-final** — `UsageLimits(request_limit=...)`.

**Still our responsibility (infra + data hygiene):**
1. **Proxy buffering headers** on the `StreamingResponse`: `Cache-Control:
   no-cache`, `X-Accel-Buffering: no`, `Connection: keep-alive`. Behind
   Cloudflare add `no-transform`. **Never** let `GZipMiddleware` front the route.
2. **Disconnect detection — verified clear.** `api/main.py` uses only
   `CORSMiddleware` (pure ASGI), so `http.disconnect` is *not* swallowed and the
   async path cancels cleanly on browser abort. Only revisit if a
   `BaseHTTPMiddleware` is added later.
3. **Tool-result size:** cap what tools return (transcript **snippets**, capped
   `browse` lists) — dumping big SQLite rows into history every turn is the #1
   context-blowup regret.
4. **Heartbeat:** confirm whether the Vercel AI data-stream needs keep-alive
   pings for long tool gaps behind idle-timeout proxies; add if needed.
5. **Cap client-sent history** length.

(Full sourced research retained in §11.)

## 8. Phasing (each independently testable)

0.5. **Spike (DO FIRST — build gate).** Throwaway end-to-end proof of the
   `VercelAIAdapter.encode_stream` ↔ `useChat` handshake on **pinned**
   `pydantic-ai` + `ai` + `@ai-sdk/react`: a `TestModel` agent that emits one
   tool-call part, streamed through the adapter, rendered by a real `useChat`
   showing text + tool + (if the model class supports it) reasoning parts. Also
   confirm the v5 `useChat`/transport signature and the consolidated data-part
   (§5/§6b). This de-risks the newest APIs before any rewrite; if the handshake
   doesn't hold, the whole frontend premise needs rethinking. Discard the spike
   code after.
1. **Retriever fix** — tokenized FTS + bm25 + `snippet()` excerpts. Independent,
   reusable, the single biggest quality win on its own; verifiable with a unit
   test. **No DB migration needed** — `knowledge_fts` is an external-content FTS5
   table (`content=knowledge_items`), so `bm25()`/`snippet()` work on the existing
   schema. (Tag filtering stays the pre-existing Python-side substring check.)
2. **`model.py` + `agent.py` + tools** — agent runnable in a script against
   `TestModel`/`FunctionModel` (no network) and live.
3. **`/api/chat` route via `VercelAIAdapter`** + headers; curl the SSE stream.
4. **Frontend** — `useChat` chat route + parts rendering (text / tool / reasoning
   / citations); FilterBar wired to `body`.
5. **Tests + docs** — backend tests with `TestModel`; update
   `docs/FRONTEND_V3_API.md` (chat now speaks the Vercel AI protocol, not the old
   custom frames).
6. **(Separate, later — NOT a chat prerequisite) Provider migration (Azure →
   OpenRouter), app-wide.** Decoupled per the resolved input: chat ships on its
   own OpenRouter `model.py` first. When tackled: simplify `config.py` to
   OpenRouter-only (`settings.llm` = LangChain `ChatOpenAI` against the OpenRouter
   endpoint); remove `azure_*` settings, the azure branch, and `llm_provider`;
   drop/replace the `requires_azure` tests; update `.env(.example)` + Docker
   `.env`. Verify the summariser still works on OpenRouter. **Low-risk:** the
   summariser is plain LCEL (`prompt_template | settings.llm`, no
   `with_structured_output`/JSON-mode — the only `response_format` is Groq audio),
   so it's a provider/config swap, not a rewrite.

## 9. Decisions (resolved)

- **Chat model + reasoning — DECIDED (reasoning model):** OpenRouter
  (OpenAI-compatible), a **reasoning + tool-calling** model via
  `settings.chat_model`, so `useChat` renders real `reasoning` parts. Azure
  dropped for chat only (the app-wide removal is decoupled). (§6b)
- **Single-item Reader chat — DECIDED (migrate to `useChat`):** the *backend*
  behaviour stays sync/full-transcript, but `ItemChat.tsx` moves off the deleted
  custom SSE consumer to `useChat`, posting `item_id` in `body.filters`;
  `/api/chat` routes it to the single-item path and wraps the output in the same
  Vercel stream (§3a). Resolves the earlier "unchanged vs. consumer removed"
  contradiction.
- **Citations — DECIDED:** **both** — inline tool-trace *and* a consolidated
  "Sources" list (the consolidated data-part to be verified against pinned Vercel
  AI SDK / Pydantic AI versions; tool-trace path is guaranteed).
- **Vercel AI SDK reuse — DECIDED:** chat-only for now. It's a chat/stream
  toolkit, isolated to the lazy-loaded Chat chunk; it does **not** touch TanStack
  Query or the rest of the app. Candidate future reuse (opt-in, not now): Reader
  item-chat, streaming resummarise output.

### Scope boundaries (v1 recommendations — confirm or override)

- **Conversation persistence — DECIDED: ephemeral.** In-memory, cleared on
  reload (same as today; `useChat` is in-memory too). DB-backed chat threads are
  explicitly out of scope for v1.
- **Feature parity:** keep the existing affordances — new chat, stop,
  regenerate (`useChat.reload`), starter prompts, filter bar. Suggested
  follow-up questions (the current UI generates them) — keep if cheap, else drop.
- **Azure cleanup — DECIDED: full migration, but DECOUPLED.** Drop Azure
  app-wide and run everything on OpenRouter — as a **separate, later** unit
  (Phase 6), **not** a chat prerequisite. Chat ships first on its own OpenRouter
  `model.py`. The summariser keeps LangChain `settings.llm`, just pointed at
  OpenRouter instead of Azure — a config/provider change, not a rewrite. Touches:
  `config.py` (remove `azure_*` settings + the azure branch + `llm_provider`;
  `settings.llm` becomes OpenRouter-only via
  `ChatOpenAI(base_url=openrouter_endpoint, …)`), the `requires_azure` pytest
  marker + any tests using it, `.env` / `.env.example`, and the Docker `.env`. No
  DB or ingest-logic changes.
- **Web search / other tools:** structurally ready (register one `@agent.tool`)
  but **not built in v1**.

## 10. Why not the raw `openai` SDK loop (considered, dropped)

A ~120-line raw loop would keep the chat path sync and add zero framework deps,
and for the **backend** it's not "too barebone" — emitting tool name/args/result
events is trivial. But the chat is greenfield and the goal is a polished
reasoning/tool-trace UI, where the real work is the **frontend** streaming
message-parts protocol + state machine. Hand-rolling that on raw SSE frames
reinvents exactly the wheel `useChat` provides. Given (a) no existing chat UI to
preserve, (b) the explicit "show reasoning + tools + params" goal, and (c)
openness to a framework that *simplifies* (without the LangChain jungle —
Pydantic AI's touched surface is tiny), the framework pays for itself here. The
costs (async chat path, two new deps, version-pinning Pydantic AI) are accepted.

## 11. Addendum — FastAPI agentic SSE research (sourced)

Sourcing: architecture-level guidance below is strong, repeated consensus
(FastAPI/Starlette source + docs, OpenAI docs, GitHub issues, blogs, r/FastAPI).
Fine-grained mechanics rest on OpenAI docs + GitHub issues. Items the framework
now handles are marked ✅; items still on us are marked ⚠️ (see §7).

- ✅ **Sync vs async generators:** Starlette threadpools sync generators; the
  trap is a *sync* blocking call inside an *async* generator. With Pydantic AI's
  async streaming + threadpooled sync tools this is handled.
- ⚠️ **Proxy/buffering:** `Cache-Control: no-cache` + `X-Accel-Buffering: no` +
  `text/event-stream`; never GZip the stream; `no-transform` behind Cloudflare;
  test through the real edge.
- ⚠️ **Client disconnect:** `BaseHTTPMiddleware` swallows `http.disconnect`
  (audit middleware). Closing a stream may not stop OpenAI-side billing.
- ✅ **Tool-call delta assembly** by `.index`; one chunk can carry both content
  and tool_calls — handled by Pydantic AI.
- ✅ **One `tool` reply per `tool_call_id`** before any other message — handled.
- ⚠️ **Context blowup:** truncate tool results before they enter history (the #1
  regret); cap client history.
- ✅ **Loop control:** cap turns + force a final answer — `UsageLimits`.
- ✅ **Frontend:** buffered chunk parsing, `[DONE]`/error handling,
  `AbortController`, no per-token `setState`, no POST auto-reconnect — handled by
  the Vercel AI SDK.
