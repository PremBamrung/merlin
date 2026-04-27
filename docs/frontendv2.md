# Merlin Frontenvdd— Development Handoff

> Generated from desk,ign session — April 22, 2026  
> Replacing the existing Streamlit frontend with a self-hostable web app.
,
---

## What Merlin Is

A **personal knowledge companion** — a local-first second brain that:
- Ingests content from YouTube, blogs, Reddit, files
- Summarizes and auto-tags everything
- Lets you chat with your entire knowledge vault (RAG)
- Acts as a daily newsletter — scanning trusted voices and surfacing what's relevant to you
- Supports agentic workflows via MCP / external tools

---

## Frontend Architecture (current prototype)

### Stack
- **Entry point:** `Merlin.html` → `styles.css` + `screen-*.jsx` components
- **Production target:** Vite + React + React Router
- **Served by:** FastAPI static mount at `/`
- **State management:** React local state (no Redux needed for MVP)

### File structure (prototype → production mapping)
```
merlin/
├── frontend/
│   ├── src/
│   │   ├── App.tsx              ← router shell
│   │   ├── styles.css           ← design tokens (copy as-is)
│   │   ├── components/
│   │   │   ├── Sidebar.tsx      ← from shared.jsx
│   │   │   ├── Topbar.tsx       ← from shared.jsx
│   │   │   ├── SourcePill.tsx   ← from shared.jsx
│   │   │   └── Icons.tsx        ← from shared.jsx (I.* components)
│   │   └── screens/
│   │       ├── Today.tsx        ← screen-today.jsx
│   │       ├── Digest.tsx       ← screen-digest.jsx
│   │       ├── Library.tsx      ← screen-library.jsx
│   │       ├── Chat.tsx         ← screen-chat.jsx (basic RAG)
│   │       ├── AgenticChat.tsx  ← screen-reddit.jsx (AgenticChatScreen)
│   │       ├── Inbox.tsx        ← screen-inbox.jsx
│   │       ├── IngestReview.tsx ← screen-ingest.jsx
│   │       ├── YouTube.tsx      ← screen-youtube.jsx
│   │       ├── Reddit.tsx       ← screen-reddit.jsx (RedditScreen)
│   │       ├── Blog.tsx         ← screen-share.jsx
│   │       ├── Graph.tsx        ← screen-graph.jsx
│   │       ├── Follows.tsx      ← screen-digest.jsx (FollowsScreen)
│   │       └── Storage.tsx      ← screen-digest.jsx (StorageScreen)
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   └── ...FastAPI app
```

### React Router routes
```
/                   → Today (home / omnibox)
/digest             → Daily digest
/library            → Library grid/list
/library/:id        → Source detail (YouTube / Blog / Reddit)
/chat               → Basic RAG chat
/chat/agentic       → Agentic chat with tools
/inbox              → Ingestion queue
/inbox/review/:id   → Ingest review (tag proposals)
/graph              → Knowledge graph
/follows            → Voices & feeds management
/settings/storage   → Storage / backend config
```

---

## Design System

### Themes
Two themes toggled via `data-theme` on `<html>`:

| Token | Obsidian (dark) | Papyrus (warm paper) |
|---|---|---|
| `--bg` | `#0f0e0d` | `#f5f0e8` |
| `--bg-1` | `#171614` | `#ede8df` |
| `--accent` | light blue (HSL 210, 75%, 72%) | warm teal-green (HSL 210, 65%, 40%) |

**Active theme in repo:** Papyrus (user preference).

### Typography
- **Display / headings:** Inter 700, tight tracking (`-0.025em`), NOT a serif font
- **UI text:** Inter 400/500/600
- **Mono / code / labels:** JetBrains Mono

### Accent color
Stored as HSL variables (`--accent-h`, `--accent-s`) so user can override via Tweaks. **Not violet** (felt too Claude-like). Light blue for Obsidian, muted teal for Papyrus.

### Key component patterns
- **Tags:** small pill with color dot + label; `existing` vs `proposed new` distinction during ingestion
- **SourcePill:** colored badge per content type (youtube / blog / reddit / web / file)
- **Cards:** `bg-1` + `border` + `border-radius: 10px`, hover lifts border to `border-accent`
- **Toggles:** custom CSS toggle (no library), `.toggle.on` = accent color
- **Confidence bars:** thin 3px bar, accent fill, shown during tag proposals + digest relevance

---

## Screen-by-Screen UX Notes

### 1. Today (home)
- **Omnibox at the top** — paste any URL, file, or type a question. Single entry point.
- Below: pending inbox items, recent library additions, quick-access chat
- Goal: zero friction. You open Merlin, paste a YouTube link, done.

### 2. Daily Digest
- Grouped sections: *Trusted voices* → *YouTube recs* → *Suggested new voices*
- Each item shows: source type, author, match %, "why this" explanation (e.g. "Matches tag: llm-research · 3 similar sources"), one-sentence summary, Ingest / Skip buttons
- Stats bar at top: N picked / N scanned / N voices / N tags matched
- Time-based: Today / Week / Archive toggle
- **Match score** = cosine similarity of video/blog embedding vs centroid of user's tag cluster embeddings

### 3. Voices & Feeds
- Per-author tracking: YouTube channel + blog RSS, mapped to tags
- Platform sources: subreddits (top weekly), YouTube subscriptions (new uploads matching tags), HN (score threshold)
- OPML import for blog feeds
- Digest schedule: time of day + delivery method (in-app / email / RSS output)

### 4. Library
- Grid / list toggle
- Filter by: source type, tag (multi-select), date range, author
- Sort by: date ingested, relevance, title
- Each card: thumbnail, title, source pill, tags, summary snippet, timestamp

### 5. Ingest Review (critical flow)
When a source is ingested, Merlin proposes:
- **Tags** — prefers existing tags, proposes new ones only if genuinely better fit
- Each proposed tag shows: confidence %, existing (count of sources) vs new, reason string
- Weak matches (< ~45% confidence) shown greyed out, not pre-selected
- **Metadata** extracted: type, duration/read-time, author, channel/site, language, published date, URL
- **Summary length** toggle: short / medium / long (regenerate button)
- **Collections** — assign to named collections (separate from tags)
- User confirms, then source lands in Library with an `.md` file written to disk

### 6. YouTube detail
- Split view: left = video info + metadata + topics + transcript; right = chat panel
- Chat is scoped to this video (timestamp-aware: "at 17:30 he says...")
- **Top comments tab**: pulls N most upvoted YouTube comments, shown with avatar, upvote count, timestamp
- "Merlin synthesized comments into N themes" button — generates a comment synthesis
- Topics = timestamped chapter markers extracted from transcript

### 7. Reddit detail
- Thread synthesis at top (Merlin's summary of the full thread)
- **Top comments** by upvotes, with reply indentation
- Auto-tag box: Merlin proposes tags during ingest, shown with dashed border + accept/decline per tag
- Note: Reddit API not implemented yet — needs scraping or official API integration

### 8. Blog detail
- Reader-mode view (clean, no nav clutter)
- Key points list (extracted by LLM)
- Related sources from vault (semantic similarity)
- **Public share modal** — generate a short link to share the summary publicly, with options: include tags, show related, expiry

### 9. Chat (RAG)
- Context source selector: which tags/sources to include in context window
- Source mode: All / Specific tags / Specific docs
- Citations inline in responses (source title + timestamp/page)
- History persisted per session

### 10. Agentic Chat
- **Tool rail** on the left sidebar — toggle individual tools on/off
- Internal tools: `search_vault`, `fetch_summary`, `cluster_insight`
- External MCP tools: `web_search`, `youtube_fetch`, `reddit_fetch`, `github_mcp`, `linear_mcp`
- **Tool trace** shown inline in chat: each tool call shows name, args, result count, latency, status (done ✓ / running spinner / error)
- "+ connect MCP server" button to add custom MCP endpoints
- Slash commands (`/command`) for quick tool invocations

### 11. Graph view
- Constellation layout: nodes = sources, edges = shared tags or semantic similarity
- Node size = connection count; color = primary tag
- Hover: shows source title + tags
- Click: opens source detail
- Filter by tag cluster

### 12. Mobile (responsive web)
- Bottom tab bar: Today / Library / Chat / More
- Same omnibox on Today
- Digest items in card list
- Library with horizontal-scroll tag chips
- **Not a native app** — same FastAPI-served HTML, responsive CSS

---

## Backend Architecture

### Storage model
```
~/merlin/vault/
├── youtube/
│   └── {slug}.md          ← one file per source
├── blogs/
│   └── {slug}.md
├── reddit/
│   └── {slug}.md
└── assets/
    └── {source-id}/       ← thumbnails, cached images
```

**Markdown file format** (frontmatter + content):
```markdown
---
id: uuid
type: youtube
url: https://youtube.com/watch?v=...
title: "State of GPT"
author: Andrej Karpathy
published: 2023-05-24
ingested: 2026-04-22
tags: [llm-research, fundamentals]
collections: [LLM research]
duration: "42:12"
language: en
summary_short: "..."
summary_medium: "..."
---

## Summary

...

## Key points

...

## Topics

- 00:04 Introduction
- ...

## Transcript

...
```

### Database schema (SQLite default, Postgres via env var)

```sql
-- Core
sources         (id, type, url, file_path, title, author, published_at, ingested_at, metadata JSONB)
summaries       (id, source_id, length ENUM, text, model, created_at)
tags            (id, name, color, created_at)
source_tags     (source_id, tag_id, confidence, auto_proposed, user_confirmed)
collections     (id, name)
source_collections (source_id, collection_id)

-- Knowledge graph
embeddings      (id, source_id, chunk_index, vector BLOB/vector(1536), model)
source_relations (source_id, related_id, score, relation_type)

-- Chat
chat_sessions   (id, title, created_at, context_mode, context_tags JSONB)
chat_messages   (id, session_id, role, content, tool_calls JSONB, citations JSONB, created_at)

-- Newsletter
followed_voices (id, name, youtube_channel, blog_url, rss_url, tags JSONB, active)
digest_runs     (id, date, items_scanned, items_picked, created_at)
digest_items    (id, run_id, source_id, match_score, why TEXT, status ENUM(pending/ingested/skipped))
```

### API endpoints needed (FastAPI)

```
# Sources
POST   /api/ingest              ← URL or file → triggers pipeline
GET    /api/sources             ← list with filters
GET    /api/sources/:id         ← detail
PATCH  /api/sources/:id         ← update tags/collections/metadata
DELETE /api/sources/:id

# Ingest review
GET    /api/ingest/pending       ← queue of unreviewed ingestions
GET    /api/ingest/:id/proposal  ← tag + metadata proposals
POST   /api/ingest/:id/confirm   ← save with confirmed tags

# Tags
GET    /api/tags                 ← all tags with counts
POST   /api/tags                 ← create new tag
PATCH  /api/tags/:id

# Chat
POST   /api/chat                 ← message → streamed response (SSE)
GET    /api/chat/sessions
GET    /api/chat/sessions/:id/messages

# Digest
GET    /api/digest/today         ← today's digest items
POST   /api/digest/refresh       ← trigger a new scan
POST   /api/digest/items/:id/ingest
POST   /api/digest/items/:id/skip

# Voices
GET    /api/follows
POST   /api/follows
PATCH  /api/follows/:id
DELETE /api/follows/:id

# Graph
GET    /api/graph/nodes          ← all sources as graph nodes
GET    /api/graph/edges          ← similarity + shared-tag edges

# Search
GET    /api/search?q=&tags=&type=   ← semantic + keyword hybrid
```

### Ingestion pipeline (per source)
```
1. fetch(url)
   ├── YouTube: yt-dlp for metadata + transcript
   ├── Blog: readability/trafilatura for clean text
   ├── Reddit: PRAW or scrape — top comments + thread
   └── File: direct read (PDF → pdfminer, md → raw)

2. summarize(text, model)  → short / medium / long summaries

3. propose_tags(text, existing_tags)
   ├── embed text → cosine sim vs existing tag centroids
   ├── if best match > 0.7 → propose existing tag
   └── if no good match → propose new tag name (LLM)

4. extract_metadata(source_type, raw)  → structured dict

5. embed_chunks(text)  → store in embeddings table

6. write_md(vault_path, frontmatter, content)

7. index_db(source, tags, embeddings)

8. notify_frontend(source_id)  → websocket or SSE
```

### Digest pipeline (runs on schedule)
```
1. For each followed voice:
   - check YouTube RSS / blog RSS for new posts since last run
   - fetch and briefly embed new content

2. For each subscription feed (Reddit, HN, YouTube subs):
   - fetch top items matching criteria

3. For each candidate item:
   - embed → cosine similarity vs user's tag centroids
   - score > threshold → include in digest
   - attach "why" string (closest tag, similar sources count)

4. Sort by score, group by section, write to digest_items

5. Serve via GET /api/digest/today
```

---

## Key Technology Choices

| Concern | Recommended | Notes |
|---|---|---|
| Backend | FastAPI + uvicorn | Already used in repo |
| DB | SQLite → Postgres | One env var: `DATABASE_URL` |
| ORM | SQLAlchemy 2.0 + Alembic | Migrations from day 1 |
| Embeddings | `sentence-transformers` local OR OpenAI `text-embedding-3-small` | Local = fully offline |
| Vector search | `sqlite-vec` (SQLite) / `pgvector` (Postgres) | No separate vector DB needed |
| LLM | Multi-provider (already in repo) — OpenAI, Anthropic, local via Ollama | |
| YouTube fetch | `yt-dlp` + `youtube-transcript-api` | |
| Blog fetch | `trafilatura` | Best for clean article extraction |
| Reddit | `PRAW` (needs API key) or scrape | Not implemented yet |
| Scheduling | `APScheduler` (in-process) or `cron` | For digest runs |
| MCP | `mcp` Python SDK | For tool integrations |
| Frontend build | Vite + React + TypeScript | Port from current Babel prototype |
| Streaming | Server-Sent Events (SSE) via FastAPI `StreamingResponse` | For chat + ingest progress |

---

## Features Not Yet Designed (backlog ideas)

- **Onboarding flow** — first run wizard: set vault path, pick LLM provider, add first voice
- **Settings page** — LLM provider keys, vault path, digest schedule, theme
- **Auth** — optional single-user password gate for self-hosted (HTTP Basic or JWT)
- **Browser extension** — right-click "Save to Merlin" from any page
- **Email digest** — cron job that emails the daily digest (SMTP)
- **RSS output** — `/api/digest/feed.xml` — pipe your digest into any reader
- **Export** — bulk export vault as zip (md files + db dump)
- **Collaboration** — shared vaults (Postgres multi-user, not planned for MVP)
- **File ingestion** — PDF, EPUB, local markdown files dropped into vault folder
- **Annotation** — highlight + annotate within source detail view

---

## MVP Scope Suggestion

**Phase 1 — core loop**
- [ ] Ingest YouTube URL → transcript → summary → tag proposal → confirm → saved to md + db
- [ ] Library view with tag filter
- [ ] Basic RAG chat against vault

**Phase 2 — newsletter**
- [ ] Follow a YouTube channel / blog RSS
- [ ] Daily digest run (manual trigger first, then scheduled)
- [ ] Ingest from digest with one click

**Phase 3 — power features**
- [ ] Agentic chat + MCP tool connections
- [ ] Graph view
- [ ] Reddit integration
- [ ] Public share links

---

## Porting the Frontend (Babel → Vite)

The prototype uses `<script type="text/babel">` — zero-build, easy to read, but not production-suitable. To port:

1. `npm create vite@latest frontend -- --template react-ts`
2. Copy `styles.css` into `src/` unchanged
3. For each `screen-*.jsx`: convert to `.tsx`, add `import React from 'react'`, replace `window.XxxScreen = XxxScreen` with `export default XxxScreen`
4. Move `shared.jsx` components to `src/components/` as named exports
5. Move `data.jsx` to `src/data/mock.ts` (replace with API calls)
6. Add React Router, map routes as listed above
7. Delete `design-canvas.jsx` — only needed for the prototype canvas

The component logic and styles transfer **verbatim**. The port is mechanical, ~30 minutes.
