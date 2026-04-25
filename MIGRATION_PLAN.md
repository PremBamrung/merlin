# Merlin: Frontend V2 Migration Continuation Plan

## Context

The app runs in Docker (FastAPI backend + Vite/React frontend). A new 10-screen frontend was partially ported from a prototype HTML mockup. 3 of 10 screens are wired to real APIs; the rest show hardcoded mock data. The backend already has more capability than the frontend uses. This plan continues the migration in priority order: first wire what the backend already supports, then add the missing backend routes, then tackle the complex pipelines implied by `frontendv2.md`.

---

## Phase 1 — Wire existing backend endpoints to the frontend (no new backend routes)

All endpoints already exist. Only frontend code and one tiny backend addition needed.

### 1a. `GET /api/tasks` → TodayPage + InboxPage

**Backend already has:** `GET /api/tasks` (list, default limit 20) and `GET /api/tasks/{id}`.

**Frontend changes:**
- `frontend/src/api/tasks.ts` — add `fetchTasks()` calling `GET /api/tasks`
- `frontend/src/pages/TodayPage.tsx` — replace `INGESTION_QUEUE` mock with `useQuery(['tasks'], fetchTasks)`. Show only non-completed tasks in the queue strip.
- `frontend/src/pages/InboxPage.tsx` — replace all mock items with the same query. Wire "Retry failed" button to existing `POST /api/sources/youtube/{id}/retry`.
- `frontend/src/pages/TodayPage.tsx` — replace "Recently added" `ALL_SOURCES` mock with `fetchKnowledge({ per_page: 4, sort: 'ingested_at' })` (already in `knowledge.ts`).

### 1b. TodayPage omnibox → real ingest

**Backend already has:** `POST /api/sources/youtube` + `POST /api/config` (returns available source types).

**Frontend changes:**
- `frontend/src/pages/TodayPage.tsx` — on omnibox Enter/submit, call `submitYouTube()` (already in `youtube.ts`) and add returned task to local queue state; navigate to `/inbox` on "View all".

### 1c. IngestReviewPage → real knowledge item load + tag save

**Backend already has:** `GET /api/knowledge/{id}` and `PATCH /api/knowledge/{id}` (updates tags/title).

**Frontend changes:**
- `frontend/src/api/knowledge.ts` — add `patchKnowledgeItem(id, { tags })` calling `PATCH /api/knowledge/{id}`.
- `frontend/src/pages/IngestReviewPage.tsx` — read `:id` from route, replace mock with `useQuery` on `fetchKnowledgeItem(id)`. Wire "Save tags" button to `patchKnowledgeItem`. Navigate from InboxPage "Open →" to `/inbox/review/:id`.
- `frontend/src/pages/InboxPage.tsx` — make "Open →" link navigate to `/inbox/review/{knowledge_item_id}` (available in task `result_data`).

### 1d. Add `GET /api/tags` backend endpoint + wire Sidebar

**Backend addition (small):** new route in `backend/api/routers/` that queries the DB for all unique tags + their counts across `KnowledgeItem.tags` JSON array. Uses raw SQL or SQLAlchemy JSON functions.

**Frontend changes:**
- `frontend/src/api/knowledge.ts` — add `fetchTags()` calling `GET /api/tags`.
- `frontend/src/components/shared/Sidebar.tsx` — replace `TAGS` import from `mockData` with `useQuery(['tags'], fetchTags)`.
- `frontend/src/pages/ChatPage.tsx` — context tag selector: replace hardcoded tag list with same `fetchTags()` query.

---

## Phase 2 — New backend routes + wire remaining screens

### 2a. Graph endpoint → GraphPage

**Backend new routes** (add file `backend/api/routers/graph.py`):
- `GET /api/graph/nodes` — return all knowledge items as nodes (id, title, source_type, tags) plus synthetic tag nodes (one per unique tag).
- `GET /api/graph/edges` — return edges: (source → tag) for each tag on each item, plus (item → item) edges when cosine similarity > threshold (Phase 3; skip for now, just return tag co-occurrence edges).

**Frontend changes:**
- `frontend/src/api/` — add `graph.ts` with `fetchGraphNodes()` and `fetchGraphEdges()`.
- `frontend/src/pages/GraphPage.tsx` — replace hardcoded nodes/edges with `useQuery`. Map to the existing SVG rendering logic.

### 2b. Source-type generic ingest (optional refactor)

If Reddit or article ingestion plugins are added later, expose `POST /api/sources/ingest` that auto-detects source type from URL using `plugin.can_handle()` across all registered plugins. TodayPage omnibox can then call this single endpoint.

---

## Phase 3 — Digest pipeline

### Backend new routes (add `backend/api/routers/digest.py`):
- `GET /api/digest/today` — MVP implementation: rank `KnowledgeItem`s by `ingested_at` descending (skip the full personalization pipeline for now), return items grouped by source_type with a placeholder `match_score` of 1.0. Real scoring (cosine sim vs tag centroids) added later when Embedding table is populated.
- `POST /api/digest/{id}/ingest` — mark item as "ingested" (no-op for now, or set a `digest_status` field).
- `POST /api/digest/{id}/skip` — mark item as "skipped".

**DB change:** Add optional `digest_status` column to `KnowledgeItem` (migration via Alembic).

**Frontend changes:**
- `frontend/src/api/` — add `digest.ts` with `fetchDigest()`, `ingestDigestItem()`, `skipDigestItem()`.
- `frontend/src/pages/DigestPage.tsx` — replace hardcoded items with real fetch; wire "Add to library" / "Skip" buttons.

---

## Phase 4 — Share feature

### Backend new routes (add `backend/api/routers/share.py`):
- `POST /api/share` — receives `knowledge_item_id`, generates a short token (UUID prefix), stores in new `ShareToken` DB table. Returns `{ token, url }`.
- `GET /api/share/{token}` — returns the public `KnowledgeItem` view (no auth needed).

**Frontend changes:**
- `frontend/src/api/` — add `share.ts` with `createShare(id)`.
- `frontend/src/pages/SharePage.tsx` — wire "Generate link" button to `createShare()`.

---

## Phase 5 — Deferred (backlog)

- Reddit ingestion plugin (new `backend/knowledge_sources/plugins/reddit/`)
- Agentic chat with MCP tool rail (`/chat/agentic` route)
- Followed voices / RSS feed management (`/follows` route)
- Semantic search via Embedding table (Phase 3 of RAG)
- Digest personalization via cosine sim on tag centroids
- Auth (single-user password gate)
- Settings page (LLM keys, vault path, digest schedule)

---

## Critical files

| File | Change |
|---|---|
| `backend/api/routers/tags.py` | **NEW** — `GET /api/tags` |
| `backend/api/routers/graph.py` | **NEW** — `GET /api/graph/nodes`, `/edges` |
| `backend/api/routers/digest.py` | **NEW** — `GET /api/digest/today`, ingest/skip |
| `backend/api/routers/share.py` | **NEW** — `POST /api/share`, `GET /api/share/{token}` |
| `backend/api/router.py` | Register new routers |
| `backend/db/models.py` | Add `digest_status` field, `ShareToken` model |
| `frontend/src/api/tasks.ts` | Add `fetchTasks()` |
| `frontend/src/api/knowledge.ts` | Add `patchKnowledgeItem()`, `fetchTags()` |
| `frontend/src/api/graph.ts` | **NEW** — graph fetch functions |
| `frontend/src/api/digest.ts` | **NEW** — digest fetch + actions |
| `frontend/src/api/share.ts` | **NEW** — share creation |
| `frontend/src/pages/TodayPage.tsx` | Wire omnibox, queue, recently added |
| `frontend/src/pages/InboxPage.tsx` | Wire task list + retry |
| `frontend/src/pages/IngestReviewPage.tsx` | Wire knowledge load + tag save |
| `frontend/src/pages/GraphPage.tsx` | Wire graph nodes/edges |
| `frontend/src/pages/DigestPage.tsx` | Wire digest fetch |
| `frontend/src/pages/SharePage.tsx` | Wire share creation |
| `frontend/src/components/shared/Sidebar.tsx` | Wire real tags from API |

---

## Verification

For each phase, after changes:
1. `docker compose up --build` — ensure both services start cleanly
2. Open `http://localhost:5173` and walk each wired screen
3. Check browser Network tab for API calls returning 200
4. For IngestReviewPage: ingest a YouTube URL, wait for task completion, then navigate to `/inbox/review/{id}` and verify real data + save tags works
5. For Digest: verify `GET /api/digest/today` returns knowledge items grouped correctly
6. For Graph: verify nodes/edges render without crashing on real data
