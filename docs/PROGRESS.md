# Merlin — Migration Progress Log

> Last updated: 2026-04-25

---

## What was done in this session

### Backend — 4 new routers

All routers are registered in `backend/api/router.py`.

| File | Endpoints added |
|---|---|
| `backend/api/tags.py` | `GET /api/tags` — aggregates unique tags + counts from all `KnowledgeItem.tags` |
| `backend/api/graph.py` | `GET /api/graph/nodes` — source + tag nodes; `GET /api/graph/edges` — item→tag + tag co-occurrence edges |
| `backend/api/digest.py` | `GET /api/digest/today` — ranked items by ingested_at (MVP); `POST /api/digest/{id}/ingest|skip` |
| `backend/api/share.py` | `POST /api/share` — generates a short token; `GET /api/share/{token}` — public item view |

### Backend — bugs fixed

| File | Fix |
|---|---|
| `backend/api/knowledge.py` | Renamed query param `source` → `source_type` to match frontend |
| `backend/api/knowledge.py` | Renamed `page_size` → `per_page` (param + response key) to match `PaginatedResponse<T>` type |

### Frontend — mock data fully eliminated

| Screen | Was | Now |
|---|---|---|
| `TodayPage` | Hardcoded queue + `ALL_SOURCES` mock | `GET /api/tasks` (polled every 3s) + `GET /api/knowledge` (4 most recent) |
| `InboxPage` | Static item list | `GET /api/tasks` live list; Retry button → `POST /api/sources/youtube/{id}/retry` |
| `IngestReviewPage` | Hardcoded item + tags | `GET /api/knowledge/:id` on load; `PATCH /api/knowledge/:id` on save; route fixed to `/inbox/review/:id` |
| `Sidebar` | `TAGS` from `mockData.ts` | `GET /api/tags` via React Query |
| `GraphPage` | Hardcoded 15 nodes/9 edges | `GET /api/graph/nodes|edges`; positions computed client-side (radial layout) |
| `DigestPage` | Static hardcoded sections | `GET /api/digest/today`; Ingest/Skip buttons wired |
| `SharePage` | `BLOGS[0]` from `mockData.ts` | `GET /api/knowledge` (most recent article); `POST /api/share` generates real public link |
| `ChatPage` | Context selector was UI-only | Tags rail now reads from `GET /api/tags` (same query as Sidebar) |

### Frontend — new API modules

- `frontend/src/api/graph.ts` — `fetchGraphNodes()`, `fetchGraphEdges()`
- `frontend/src/api/digest.ts` — `fetchDigest()`, `ingestDigestItem()`, `skipDigestItem()`
- `frontend/src/api/share.ts` — `createShare(knowledgeItemId)`

### Frontend — existing API modules updated

- `frontend/src/api/tasks.ts` — added `fetchTasks(limit)`
- `frontend/src/api/knowledge.ts` — added `patchKnowledgeItem(id, updates)`, `fetchTags()`
- `frontend/src/api/youtube.ts` — updated `submitYouTube()` to accept object or string; added `retryYouTube(itemId)`
- `frontend/src/types/index.ts` — extended `Task` type with `task_type`, `knowledge_item_id`, timestamps; added `Tag` interface

### Routing fix

- `App.tsx`: `/ingest` → `/inbox/review/:id` (IngestReviewPage now receives a real knowledge item ID)

---

## Current state by screen

| Screen | API wired | Notes |
|---|---|---|
| `TodayPage` | ✅ | Omnibox ingests YouTube URLs; queue polled live; recent items real |
| `InboxPage` | ✅ | Live task list; retry wired for YouTube items |
| `IngestReviewPage` | ✅ | Loads real item; saves tags via PATCH |
| `LibraryPage` | ✅ (was already done) | Full CRUD + search + filter |
| `ChatPage` | ✅ (streaming was already done) | Context selector tags now real; narrowing context not yet sent to API |
| `YouTubePage` | ✅ (was already done) | Ingest form + task polling |
| `GraphPage` | ✅ | Real nodes/edges; layout is radial (simple, not force-directed) |
| `DigestPage` | ✅ | Real items; scoring is placeholder (1.0) until embeddings exist |
| `SharePage` | ✅ | Real knowledge item; real share token; copy-to-clipboard |
| `RedditPage` | ❌ | Still hardcoded — no Reddit ingestion plugin yet |

---

## What is left to do

### High priority

#### 1. ChatPage context narrowing
- **What:** The context selector (left rail) already shows real tags from `GET /api/tags`, but selecting a tag doesn't actually filter the RAG query.
- **Fix needed:** Pass selected `tags` / `source_types` as `context_filters` in the `POST /api/chat` body. The backend already supports `context_filters`.
- **Files:** `frontend/src/pages/ChatPage.tsx`, `frontend/src/api/chat.ts`

#### 2. InboxPage — `Open →` for non-YouTube tasks
- **What:** `Open →` only works when `knowledge_item_id` is populated (YouTube completed tasks). For future source types, ensure `result_data.knowledge_item_id` is always filled.
- **Files:** Backend task completion hooks for each plugin.

#### 3. Share tokens — persistence across restarts
- **What:** `backend/api/share.py` uses an in-memory dict. Tokens are lost on server restart.
- **Fix needed:** Add a `share_tokens` table (migration `002_add_share_tokens.py`), store token + expiry + item_id.
- **Files:** `backend/db/models.py`, new Alembic migration, `backend/api/share.py`

---

### Medium priority

#### 4. Digest personalization (real scoring)
- **What:** `GET /api/digest/today` currently returns items sorted by `ingested_at` with `match_score: 1.0`. The `frontendv2.md` spec calls for cosine similarity against tag centroids.
- **Fix needed:** Populate the `embeddings` table during ingestion, then compute cosine sim at digest time.
- **Files:** `backend/api/digest.py`, `backend/rag/` (Phase 3 retriever), YouTube plugin summarizer

#### 5. Graph layout — force-directed
- **What:** GraphPage uses a static radial layout. With many nodes it will look cluttered.
- **Fix needed:** Implement a basic D3-style force simulation (or use `d3-force` package) in the frontend layout function.
- **Files:** `frontend/src/pages/GraphPage.tsx`

#### 6. Library item detail page
- **What:** `frontendv2.md` defines `/library/:id` as a split-view page (transcript + topics left, chat right) for YouTube; summary view for articles.
- **Fix needed:** New `LibraryItemPage.tsx` route + page. Backend already has `GET /api/knowledge/:id` with `raw_content`.
- **Files:** `frontend/src/pages/LibraryItemPage.tsx` (new), `frontend/src/App.tsx`

#### 7. Sidebar counts (Library, Inbox, Digest)
- **What:** Sidebar shows hardcoded numbers for Library (248), Digest (12), Inbox (3).
- **Fix needed:** Drive from `GET /api/knowledge?per_page=1` (total field), `GET /api/tasks` (active count), `GET /api/digest/today` (total field).
- **Files:** `frontend/src/components/shared/Sidebar.tsx`

---

### Lower priority (Phase 5 backlog)

#### 8. Reddit ingestion plugin
- **What:** No Reddit plugin exists. `RedditPage` is still 100% mocked.
- **Fix needed:** New `backend/knowledge_sources/plugins/reddit/` plugin using PRAW or scraping. Register in `main.py`.

#### 9. Agentic chat + MCP tool rail
- **What:** `frontendv2.md` defines `/chat/agentic` with a tool-call trace panel.
- **Fix needed:** New route + page; backend needs MCP-compatible tool invocation layer.

#### 10. Followed voices / RSS feed management
- **What:** `/follows` route not implemented. Digest currently has no "voices" concept.
- **Fix needed:** `followed_voices` DB table, RSS polling service, `GET/POST /api/follows` endpoints, new `FollowsPage`.

#### 11. `GET /api/sources/ingest` — generic URL endpoint
- **What:** TodayPage omnibox currently only submits YouTube URLs. A generic endpoint would auto-detect source type using `plugin.can_handle()`.
- **Fix needed:** New router entry that loops through `registry.all()` and delegates to the matching plugin.
- **Files:** `backend/api/sources/` (new `ingest.py`), `frontend/src/pages/TodayPage.tsx`

#### 12. Auth (single-user password gate)
- **What:** No auth on any endpoint. Anyone on the same network can access the vault.
- **Fix needed:** Simple API key or HTTP Basic Auth middleware in FastAPI.

#### 13. Settings page
- **What:** No `/settings` route. LLM keys, vault path, digest schedule are only configurable via env vars.
- **Fix needed:** New `SettingsPage.tsx` + `GET/PATCH /api/settings` endpoints.

#### 14. Article / PDF ingestion plugins
- **What:** Only YouTube plugin is registered. `source_type: 'article'` and `'pdf'` have no ingest path.
- **Fix needed:** Article plugin (trafilatura-based), PDF plugin (pdfminer/pymupdf).

---

## How to run

```bash
docker compose up --build
# Frontend:  http://localhost:5173
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

To verify each screen works end-to-end:
1. Go to `/today` → paste a YouTube URL → watch queue update live
2. Go to `/inbox` → see task list update; click "Open →" on a completed task
3. Go to `/inbox/review/:id` → real summary + tags loaded; save updates the item
4. Go to `/library` → search, filter, delete all work
5. Go to `/graph` → real nodes/edges rendered from your library
6. Go to `/digest` → real items listed from library
7. Go to `/share` → click "Share public" → copy the generated link
8. Go to `/chat` → ask anything → SSE streaming response with citations
