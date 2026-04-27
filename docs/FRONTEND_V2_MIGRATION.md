# Frontend v2 Migration Notes

## What was done

Replaced the old `frontend/` (React + Vite + Tailwind, 2 screens) with a new `frontend/` built from the `frontend_v2/` prototype. The prototype was a single-HTML CDN-React mockup; the new app is a proper Vite + React 18 + TypeScript project.

**Stack:** React 18, React Router v6, TypeScript, Vite, plain CSS (v2 design system), Zustand, TanStack React Query, Axios, react-markdown.

**10 screens ported:** Today, Digest, Inbox, Library, Chat, Graph, YouTube-ingest, Reddit, IngestReview, Share.

`Dockerfile.frontend` and `docker-compose.yml` were not changed.

---

## What is wired to real APIs

| Screen | Endpoint(s) |
|---|---|
| `ChatPage` | `POST /api/chat` (SSE streaming) |
| `LibraryPage` | `GET /api/knowledge`, `DELETE /api/knowledge/{id}` |
| `YouTubePage` | `POST /api/sources/youtube`, `GET /api/tasks/{id}` |

---

## What still uses mock/static data (needs real backends)

All other screens show hardcoded content from `src/data/mockData.ts`. Each needs a backend route + real fetch.

### `TodayPage` (`src/pages/TodayPage.tsx`)
- **Ingestion queue** — hardcoded 3 items. Should poll `/api/tasks` (active tasks list) or a new `GET /api/inbox/queue` endpoint.
- **Recently added** — pulls from `ALL_SOURCES` mock. Should call `GET /api/knowledge?per_page=4&sort=ingested_at`.
- **Omnibox** — Enter key adds to local queue state only. Should submit to `/api/sources/youtube` (or a generic `/api/sources/ingest` that auto-detects type).

### `DigestPage` (`src/pages/DigestPage.tsx`)
- Entire digest is static. Needs a `GET /api/digest` endpoint that returns ranked, personalized picks.
- Stats (12 picked, 47 scanned, etc.) are hardcoded.

### `InboxPage` (`src/pages/InboxPage.tsx`)
- Items are hardcoded. Should call `GET /api/tasks` to list in-progress/done/failed ingestion tasks.
- "Retry failed" and "Approve all" buttons are no-ops.
- Auto-ingest rules are static UI — needs a `/api/rules` CRUD endpoint.

### `GraphPage` (`src/pages/GraphPage.tsx`)
- Nodes and edges are hand-composed static data. Should derive from `GET /api/knowledge/graph` (tags + source relationships).
- Cluster insight text is hardcoded.

### `RedditPage` (`src/pages/RedditPage.tsx`)
- Shows a single hardcoded Reddit thread. Should load a real `KnowledgeItem` by id from `GET /api/knowledge/{id}` (once Reddit ingestion is supported).

### `IngestReviewPage` (`src/pages/IngestReviewPage.tsx`)
- Shows a hardcoded post-ingest review UI. Should receive a `knowledge_item_id` (from task result) and load it via `GET /api/knowledge/{id}`, then allow patching tags via `PATCH /api/knowledge/{id}`.
- Currently not reachable from a natural flow — should be navigated to after a task completes (e.g., from YouTubePage on success, or InboxPage "Open →").

### `SharePage` (`src/pages/SharePage.tsx`)
- Shows `BLOGS[0]` hardcoded. Should load a real `KnowledgeItem` for article/blog type.
- Share link (`merlin.vault/s/...`) is fake — needs a `POST /api/share` endpoint that returns a public token.

---

## `src/data/mockData.ts`

This file (`VIDEOS`, `BLOGS`, `REDDITS`, `ALL_SOURCES`, `TAGS`) is only used by stub screens and `Sidebar.tsx` for the static tag list. Once real endpoints exist:

- Replace `ALL_SOURCES` usages with `fetchKnowledge()` calls.
- Replace `TAGS` in `Sidebar.tsx` with a `GET /api/tags` or derived from the knowledge list.
- Delete the file once all screens are wired.

---

## Sidebar tag counts

`Sidebar.tsx` imports `TAGS` from `mockData.ts` for the tag list. These counts (34, 22, etc.) are fake. When a `GET /api/tags` endpoint exists, replace with a real fetch.

---

## Source types

The backend uses `source_type: 'youtube' | 'article' | 'pdf'`. The v2 design uses `'youtube' | 'blog' | 'reddit'`. `SourcePill.tsx` already maps `article → blog`. Reddit ingestion doesn't exist yet on the backend — add mapping when it does.

---

## Next backend features implied by the UI

1. `GET /api/tasks` — list all tasks (for Inbox and Today queue)
2. `PATCH /api/knowledge/{id}` — update tags/metadata (for IngestReview)
3. `GET /api/knowledge/graph` — tag + source relationship graph (for Graph screen)
4. `GET /api/digest` — ranked personalized feed (for Digest screen)
5. `POST /api/share` — create public share token (for Share screen)
6. `GET /api/tags` — tag list with counts (for Sidebar)
7. Reddit source ingestion (for Reddit screen to show real content)
