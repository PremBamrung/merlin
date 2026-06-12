# Frontend v3 — API & Streaming Contract

> The wire contract between the FastAPI layer (`api/`) and the `web/` frontend.
> Companion to `FRONTEND_V3_PLAN.md` (stack/arch), `FRONTEND_V3_PATTERNS.md`
> (how the client consumes this), `FRONTEND_V3_SCREENS.md`, `FRONTEND_V3_DESIGN_SYSTEM.md`.
>
> **Scope.** Per-endpoint request/response *bodies* are auto-generated into the
> typed client via `openapi-typescript` (`npm run gen:api` → `lib/api/schema.d.ts`)
> — so this doc does **not** hand-spec every JSON field. It pins the things
> OpenAPI can't express well and that the frontend depends on:
> 1. the **SSE wire format** for chat tokens and task progress,
> 2. the **canonical JSON shapes** the frontend treats as contracts (item, task),
> 3. a **consistent error envelope** the `ErrorState` component consumes,
> 4. the **endpoint map** and which existing `merlin.services` call backs each.
>
> **Design rule.** The API is a *thin* adapter over `merlin.services`. A router
> validates input, calls one service function, and serialises the plain dict the
> service already returns. No business logic in routers. If a shape isn't here,
> it's whatever the service's `serialize_*` produces — that is the source of truth.

---

## 1. Conventions

- **Base path**: all endpoints under `/api`. OpenAPI at `/openapi.json`,
  interactive docs at `/docs` (dev only).
- **Content type**: `application/json` for request/response bodies;
  `text/event-stream` for the two streaming endpoints (§4).
- **IDs**: opaque strings (UUIDs). `source_id` is the per-source natural key
  (e.g. the YouTube video id); `(source_type, source_id)` is the dedup key.
- **Timestamps**: ISO-8601 strings (already what services emit via `.isoformat()`),
  or `null`. The client formats; the server never sends epoch ints.
- **JSON-in-text fields**: `tags` is a JSON array, `topics`/`timestamps` are JSON
  objects. Services already parse these from the DB's `Text` columns into real
  arrays/objects before serialising — **the API always sends parsed JSON, never
  a stringified blob.**
- **Pagination**: list endpoints return `{ items, total, page, per_page }`
  (matches `library.list_items`). The client derives page count from `total`.
- **No auth in Tier 0.** Single-user vault behind the NAS. A later tier can add
  a session cookie / token without changing these shapes.

---

## 2. Canonical resource shapes

These mirror the service serializers verbatim — the frontend types are generated
from them, so keep router responses byte-compatible with these dicts.

### 2.1 `Item` (from `library.serialize_item`)

```jsonc
{
  "id": "…",
  "source_type": "youtube",
  "source_id": "Qm4h0R1kMDc",
  "title": "…",
  "author": "…",                 // nullable
  "published_at": "2025-…T…Z",   // nullable ISO
  "ingested_at": "2026-…T…Z",    // nullable ISO; drives "Newest" sort
  "summary": "…markdown…",       // nullable until summarised
  "summary_length": "short",     // short | medium | long
  "tags": ["ai", "python"],      // parsed JSON array
  "topics": { "…": "…" },        // parsed JSON object
  "llm_model": "deepseek/…",     // nullable
  "word_count": 1944,            // nullable
  "status": "completed",         // see status enum below
  "error_message": null,         // populated when status = failed

  // YouTube-specific — null for non-youtube sources
  "channel": "…",
  "views": 123456,
  "duration": 1019,              // seconds
  "subscribers": 1200000,
  "videos_count": 803,
  "thumbnail_url": "https://…",
  "detected_language": "en",
  "timestamps": { "Overview": 0, "Key point": 134 },  // parsed JSON object

  // present ONLY on GET /api/items/{id} (include_content=True)
  "raw_content": "…full transcript…"
}
```

**`status` enum** (single source for the status-dot styling in the design system):
`queued` · `processing` · `completed` · `failed`
(plus `pending` reserved). `failed` ⇒ `error_message` is set and the Reader/Inbox
render the `ErrorState` with that message + Retry.

List endpoints return `Item` **without** `raw_content`; the detail endpoint
includes it (`get_item` calls `serialize_item(include_content=True)`).

### 2.2 `Task` (from `ingest._serialize_task`)

```jsonc
{
  "id": "…",                     // task_id returned by ingest/resummarize
  "task_type": "ingest_youtube", // | "resummarize_youtube"
  "status": "processing",        // queued | processing | completed | failed
  "progress": 62,                // 0–100 int
  "message": "Downloading audio for transcription…",  // nullable human string
  "error": null,                 // populated on failure
  "knowledge_item_id": "…",      // nullable until the item row exists
  "created_at": "2026-…T…Z",     // nullable ISO
  "result_data": null            // parsed JSON, present on completion
}
```

This is the exact payload the SSE progress stream (§4.2) emits per event and the
poll endpoint (`GET /api/tasks/{id}`) returns.

### 2.3 `Citation` (chat)

Derived from the retriever's `RetrievedChunk`. Minimum fields the
`CitationCard` needs (final names settled when the router is written):

```jsonc
{
  "item_id": "…",          // → opens Reader at /library/:id
  "title": "…",
  "source_type": "youtube",
  "snippet": "…matched passage…",
  "score": 0.0             // optional relevance score
}
```

---

## 3. Endpoint map (→ backing service)

Every Tier-0 endpoint wraps an **existing** `merlin.services` function — the
first cut needs no new backend logic.

| Method & path | Service | Notes |
|---|---|---|
| `GET /api/items` | `library.list_items` | query: `search, sort, source_type, status, tags[], page, per_page` → `{items,total,page,per_page}` |
| `GET /api/items/{id}` | `library.get_item` | includes `raw_content`; `404` if missing |
| `PATCH /api/items/{id}` | `library.update_item` | body `{ tags?, title? }` → updated `Item` (optimistic on client) |
| `DELETE /api/items/{id}` | `library.delete_item` | `204` on success, `404` if missing |
| `POST /api/items/{id}/clear-summary` | `library.clear_summary` | |
| `POST /api/ingest/youtube` | `ingest.submit_youtube` | body `{ url, languages[], summary_length }` → `{ task_id }`. **Server-side dedup**: already-ingested → re-summarise path, same `{task_id}` shape |
| `POST /api/items/{id}/resummarize` | `ingest.resummarize` | body `{ summary_length?, languages? }` → `{ task_id }` |
| `POST /api/items/{id}/retry` | `ingest.retry` | failed item → `{ task_id }` |
| `GET /api/tasks` | `ingest.recent_tasks` | `?limit=` → `Task[]` |
| `GET /api/tasks/{id}` | `ingest.get_task` | poll fallback; `404` if missing |
| `GET /api/tasks/{id}/stream` | (wraps `get_task`) | **SSE** progress — §4.2 |
| `POST /api/chat` | `chat.answer` | body `{ question, history[], filters }` → **SSE** — §4.1 |
| `GET /api/tags` | `library.list_tags` | `[{ name, count }]` |
| `GET /api/source-types` | `library.list_source_types` | `[{ source_type, count }]` for sidebar |
| `GET /api/insights/timeline` | `library.ingest_timeline` | Tier 1 |
| `GET /api/insights/top-channels` | `library.top_channels` | Tier 1 |
| `GET /api/insights/status-counts` | `library.status_counts` | Tier 1 |
| `GET /api/insights/channel-count` | `library.count_channels` | Tier 1 |

Tier-2 routes (`/api/graph`, `/api/wiki`, semantic search) are deferred — they
need the embeddings/wiki layer that doesn't exist yet.

---

## 4. Streaming (SSE) — the part OpenAPI can't express

Both streams use Server-Sent Events (`Content-Type: text/event-stream`). Each
message is a `data:` line carrying **one JSON object**, frames separated by a
blank line (`\n\n`). Every object has a `type` discriminator. The client's `sse()`
helper (in `FRONTEND_V3_PATTERNS.md` §4) yields these parsed objects; consumers
switch on `type`.

> Why SSE and not WebSocket: both flows are **server→client, one-way** (token
> fan-out, progress fan-out). SSE is a plain HTTP response — trivial to emit from
> FastAPI (`StreamingResponse`), survives proxies, auto-reconnects. No WS upgrade
> needed. Chat is a `POST` that returns an event stream (fetch + `ReadableStream`,
> not `EventSource`, since `EventSource` can't POST a body).

### 4.1 Chat — `POST /api/chat`

**Request**
```jsonc
{
  "question": "What did the DJI video say about moats?",
  "history": [
    { "role": "user", "content": "…" },
    { "role": "assistant", "content": "…" }
  ],
  "filters": { "source_types": ["youtube"], "tags": ["ai"] }   // both optional
}
```

Backed by `chat.answer(question, history, filters) -> (token_gen, citations)`.
The router emits `citations` first (they're known before streaming — `answer`
retrieves chunks synchronously, *then* returns the generator), streams tokens,
then closes with `done`.

**Event sequence**
```
data: {"type":"citations","citations":[ {Citation…}, … ]}

data: {"type":"token","text":"DJI's "}

data: {"type":"token","text":"edge "}

…

data: {"type":"done"}
```

| `type` | Fields | Meaning |
|---|---|---|
| `citations` | `citations: Citation[]` | sent once, up front (may be `[]`) |
| `token` | `text: string` | append to the in-flight assistant bubble |
| `done` | — | stream complete; re-enable composer |
| `error` | `error: ErrorBody` (§5) | LLM/retrieval failure mid-stream; client shows inline retry preserving the question |

Client (`useChatStream`): on a new question, **abort** the prior fetch; disable
the composer while streaming; render the token cursor; on `done` resolve, on
`error` surface §5 inline.

> **Citations-first vs citations-last is a real choice.** `answer` returns the
> citation list *before* the token generator runs, so emitting `citations` first
> lets the rail render immediately and avoids a layout jump at the end. The
> `SCREENS` doc shows the rail "after the stream" — either is acceptable; the
> contract guarantees citations arrive **no later than `done`**.

### 4.2 Task progress — `GET /api/tasks/{id}/stream`

The router polls `ingest.get_task(id)` server-side on an interval and pushes a
`progress` event whenever `status`/`progress`/`message` changes, then a terminal
event. Payload is the full §2.2 `Task` object so the client never needs a second
fetch.

**Event sequence**
```
data: {"type":"progress","task":{ …Task, "status":"processing","progress":62 }}

data: {"type":"progress","task":{ …Task, "progress":80 }}

data: {"type":"complete","task":{ …Task, "status":"completed","knowledge_item_id":"…" }}
```

| `type` | Fields | Meaning |
|---|---|---|
| `progress` | `task: Task` | a tick; `TaskRow` updates bar + message |
| `complete` | `task: Task` | terminal **success**; `status:"completed"` |
| `failed` | `task: Task` | terminal **failure**; `task.error` is the real message |

On `complete`/`failed` the server closes the stream. `useTaskProgress`:
toast the outcome, invalidate `keys.items` (and `keys.item(knowledge_item_id)`),
and for `failed` surface `task.error` in the Inbox card / Reader `ErrorState`.

**Fallback**: if the stream drops, the client falls back to polling
`GET /api/tasks/{id}` until a terminal status — same `Task` shape, so no extra
code path beyond the poll loop.

---

## 5. Error envelope

One consistent shape for **all** non-2xx JSON responses *and* the SSE `error`
event, so a single `ErrorState` renders every failure.

```jsonc
{
  "error": {
    "code": "not_found",          // machine-readable, snake_case (see table)
    "message": "Item not found.", // human string — safe to display verbatim
    "detail": null                // optional: validation field errors, upstream text
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `invalid_input` | bad URL, unsupported language, malformed body. `detail` carries per-field messages. Mirrors `ValueError` from `submit_youtube`/`validate_input` |
| 404 | `not_found` | unknown item/task id |
| 409 | `conflict` | (reserved) duplicate that isn't auto-resolved |
| 422 | `validation_error` | FastAPI/Pydantic request-model failure; `detail` = FastAPI's field list |
| 502 | `upstream_error` | LLM / yt-dlp / Groq failure. `message` = the real upstream error so the Reader/Inbox can show *why* ingest failed |
| 500 | `internal_error` | unexpected; generic message, `detail` null in prod |

**Service-exception mapping** (where the router translates):
- `ValueError` from a service → `400 invalid_input` with `message = str(e)`.
- Missing row (service returns `None`/`False`) → `404 not_found`.
- Anything else escaping a service → `500 internal_error` (logged server-side,
  generic message client-side).

**Ingest is special**: a *failed ingest task* is **not** an HTTP error — the
`POST /api/ingest/youtube` call succeeds (`200 {task_id}`); the failure surfaces
later as a `failed` SSE event with `task.error`. The frontend shows it on the
`TaskRow`/Inbox card, not as a request error. This matches the existing async
task model (the plugin runs off-thread and records failure on the `Task` row).

---

## 6. What the frontend may assume (contract guarantees)

1. **List item ≠ detail item**: `raw_content` is present **only** on
   `GET /api/items/{id}`. Don't expect transcripts in the grid.
2. **JSON fields are parsed**: `tags` (array), `topics`/`timestamps` (objects)
   arrive as real JSON, never strings.
3. **`ingested_at` drives Newest**: re-summarise bumps it server-side; after a
   `complete` event, invalidating `keys.items` re-sorts correctly.
4. **Dedup is invisible**: posting an already-ingested URL still returns a
   `{task_id}`; the only signal is `task_type:"resummarize_youtube"`, which the
   toast can use to say "Already in library — re-summarising".
5. **Citations arrive no later than `done`** on the chat stream (§4.1).
6. **Terminal task events carry the full `Task`**, including
   `knowledge_item_id`, so the client can navigate to the new Reader without an
   extra round-trip.
7. **Every error is the §5 envelope** — one `ErrorState` handles them all.

---

## 7. Open questions to settle when writing `api/`

- **Citation field names** (§2.3) — finalise against `RetrievedChunk` attributes
  when the chat router is implemented.
- **Progress push cadence** for `/tasks/{id}/stream` — interval poll of
  `get_task` vs hooking the task queue's `report()` callback directly. Start with
  a ~500ms–1s server-side poll (simplest, no queue changes); upgrade to a
  push/queue listener only if it feels laggy.
- **`history` cap** — bound turns sent to `chat.answer` to control context size
  (client-side trim before POST).
- **CORS** — dev runs `web/` (Vite, :5173) and `api/` (uvicorn, :8000) on
  different origins; enable `CORSMiddleware` for the dev origin. In prod the
  FastAPI app serves the built `web/` as static files (same origin → no CORS).
