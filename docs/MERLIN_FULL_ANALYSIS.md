# Merlin — Full Project Analysis
> Date: 2026-04-26 | Branch: develop | Author: Claude Sonnet 4.6

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Backend: Complete Implementation Status](#3-backend-complete-implementation-status)
4. [Frontend v2: Complete Implementation Status](#4-frontend-v2-complete-implementation-status)
5. [Full v2 Migration Checklist](#5-full-v2-migration-checklist)
6. [Frontend v2 UI/UX Analysis & Improvements](#6-frontend-v2-uiux-analysis--improvements)
7. [Enhancing Merlin with Karpathy's LLM Wiki](#7-enhancing-merlin-with-karpathys-llm-wiki)
8. [Phased Roadmap](#8-phased-roadmap)

---

## 1. Executive Summary

Merlin is a personal knowledge management platform — a self-hosted vault that ingests YouTube videos (and eventually articles, PDFs, Reddit threads) and makes them queryable via RAG chat, browsable via a library, and explorable via a knowledge graph.

**Current state**: The backend is production-grade with 20+ API endpoints, an async task queue, an LLM plugin architecture, FTS5 full-text search, and solid data models. The React v2 frontend is wired to the real API on 9 of 11 screens. The design system is polished and themeable (Obsidian dark + Papyrus warm-light). The codebase is clean, well-structured, and ready to ship incrementally.

**Completion estimate**:

| Layer | Status | % Done |
|---|---|---|
| Backend API surface | Implemented + tested | ~90% |
| Frontend wiring to real API | Wired (9/11 pages) | ~82% |
| Core features (YouTube ingest + RAG chat) | Fully functional | ~95% |
| Advanced features (embeddings, digest personalization) | Stubbed/placeholder | ~20% |
| New source plugins (article, PDF, Reddit) | Missing | 0% |
| Frontend UX completeness | Good but lacking | ~65% |
| Karpathy-style compounding knowledge | Not started | 0% |

**What's blocking a "done" feeling**: (a) the library doesn't grow because only YouTube is supported; (b) chat retrieval is flat FTS5 — it doesn't get smarter as you add more items; (c) the digest is purely chronological, not personalized; (d) the UI has significant wasted screen real estate on wide monitors; (e) the "Sources" section in the sidebar links to Reddit (no backend) and confusingly to `/share` for blogs.

---

## 2. Architecture Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                         BROWSER (port 5173)                        │
│  React 18 + TypeScript + Vite + React Router v6 + TanStack Query   │
│                                                                     │
│  Sidebar ─── Today / Digest / Inbox / Library / Chat / Graph       │
│              YouTube / Reddit (mock) / Share                       │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ HTTP/SSE (Axios)
┌──────────────────────────────▼─────────────────────────────────────┐
│                        FASTAPI (port 8000)                         │
│                                                                     │
│  /api/health          /api/config                                  │
│  /api/knowledge       /api/tags          /api/tasks                │
│  /api/sources/youtube /api/chat          /api/digest               │
│  /api/graph           /api/share                                   │
│                                                                     │
│  Plugin Registry ──► YouTubePlugin (extractors + summarizer)       │
│  TaskQueue (ThreadPoolExecutor, max 3 workers)                     │
│  HybridRetriever (FTS5 now, vectors Phase 3)                       │
│  LLM (Azure OpenAI | OpenRouter, LangChain)                        │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ SQLAlchemy
┌──────────────────────────────▼─────────────────────────────────────┐
│                       SQLite (merlin.db)                           │
│                                                                     │
│  KnowledgeItem  ──1:1──► YouTubeMetadata                          │
│  KnowledgeItem  ──1:N──► BackgroundTask                           │
│  KnowledgeItem  ──1:N──► Embedding (unpopulated — Phase 3)        │
│  knowledge_fts (FTS5 virtual table — auto-synced via triggers)     │
└────────────────────────────────────────────────────────────────────┘
```

### Data flow summary

**Ingestion**: `POST /api/sources/youtube` → TaskQueue enqueues worker → YouTubePlugin extracts metadata + subtitles (or Groq audio fallback) → LLM generates summary + topics → persist KnowledgeItem + YouTubeMetadata → task marked complete.

**Retrieval (chat)**: `POST /api/chat` with messages → HybridRetriever runs FTS5 MATCH on title/summary/content → top-5 excerpts formatted into RAG context → LLM streams response → citations emitted as SSE events.

**Display**: React Query fetches paginated lists or single items → renders with real thumbnail, duration, tags, summary.

---

## 3. Backend: Complete Implementation Status

### 3.1 API Endpoints

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/api/health` | GET | ✅ Done | Returns `{status:"ok", version:"2.0.0"}` |
| `/api/config` | GET | ✅ Done | Lists registered source plugin schemas |
| `/api/knowledge` | GET | ✅ Done | Paginated, filterable (type, search, tags, status) |
| `/api/knowledge/{id}` | GET | ✅ Done | Full item incl. raw_content |
| `/api/knowledge/{id}` | PATCH | ✅ Done | Update tags / title |
| `/api/knowledge/{id}` | DELETE | ✅ Done | Hard delete + cascade |
| `/api/tags` | GET | ✅ Done | All tags with counts |
| `/api/tasks` | GET | ✅ Done | Recent tasks list |
| `/api/tasks/{id}` | GET | ✅ Done | Single task poll |
| `/api/sources/youtube` | POST | ✅ Done | Enqueue ingestion |
| `/api/sources/youtube` | GET | ✅ Done | List YouTube items |
| `/api/sources/youtube/{id}` | GET | ✅ Done | Single YouTube item |
| `/api/sources/youtube/{id}/retry` | POST | ✅ Done | Retry failed task |
| `/api/sources/youtube/{id}/summary` | DELETE | ✅ Done | Clear summary only |
| `/api/chat` | POST | ✅ Done | SSE streaming RAG chat |
| `/api/digest/today` | GET | ✅ Done (MVP) | Returns chronological list, all scores=1.0 |
| `/api/digest/{id}/ingest` | POST | ⚠️ Placeholder | No-op, needs real state |
| `/api/digest/{id}/skip` | POST | ⚠️ Placeholder | No-op, needs real state |
| `/api/graph/nodes` | GET | ✅ Done | Items + tag nodes |
| `/api/graph/edges` | GET | ✅ Done | Item→tag + tag co-occurrence edges |
| `/api/share` | POST | ⚠️ In-memory | Token lost on restart — needs DB |
| `/api/share/{token}` | GET | ⚠️ In-memory | Same issue |

### 3.2 Services & Infrastructure

| Component | Status | Notes |
|---|---|---|
| YouTube metadata extraction | ✅ Done | pytube + channel stats |
| YouTube subtitle extraction | ✅ Done | 30+ languages |
| Audio transcription fallback | ✅ Done | Groq Whisper |
| LLM summarization | ✅ Done | Azure OpenAI + OpenRouter |
| Topic/timestamp extraction | ✅ Done | JSON from LLM |
| Background task queue | ✅ Done | ThreadPoolExecutor, progress callbacks |
| FTS5 full-text search | ✅ Done | Triggered virtual table |
| Vector embeddings | ❌ Missing | Table exists, never populated |
| Vector retrieval (HybridRetriever Phase 3) | ❌ Missing | FTS5-only path active |
| Article plugin | ❌ Missing | Schema defined, no implementation |
| PDF plugin | ❌ Missing | Schema defined, no implementation |
| Reddit plugin | ❌ Missing | No plugin, no API |
| Share token persistence | ❌ Missing | In-memory dict |
| Settings API | ❌ Missing | No `/api/settings` endpoint |
| Auth layer | ❌ Missing | `app_password` in config, no middleware |
| Concept synthesis job | ❌ Missing | Not started (Karpathy layer) |

### 3.3 Database — What Needs Adding

| Migration | Priority | Why |
|---|---|---|
| `share_tokens` table (id, token, knowledge_item_id, created_at) | HIGH | Share tokens lost on restart |
| `digest_actions` table (item_id, action, timestamp) | MEDIUM | Track skip/ingest history for personalization |
| `concept_pages` table | LOW-FUTURE | Karpathy synthesis layer |
| `followed_sources` table | LOW | For RSS / channel subscriptions |

---

## 4. Frontend v2: Complete Implementation Status

### 4.1 Pages

| Page | Route | API Wired | Functional | Issues |
|---|---|---|---|---|
| TodayPage | `/today` | ✅ | ✅ | Chat redirect doesn't pass the typed query |
| DigestPage | `/digest` | ✅ | ✅ | All scores are 1.0 (backend MVP) |
| InboxPage | `/inbox` | ✅ | ✅ | Retry button → correct endpoint |
| LibraryPage | `/library` | ✅ | ✅ | Pagination: only fetches per_page=50, no load-more |
| LibraryItemPage | `/library/:id` | ✅ | ✅ | Tag editing works |
| ChatPage | `/chat` | ✅ | ⚠️ | Context filters UI exists but not sent to API |
| GraphPage | `/graph` | ✅ | ✅ | Layout is non-interactive radial, not force-directed |
| YouTubePage | `/youtube` | ✅ | ✅ | Full flow working |
| IngestReviewPage | `/inbox/review/:id` | ✅ | ✅ | — |
| SharePage | `/share` | ✅ | ⚠️ | Tokens lost on server restart |
| RedditPage | `/reddit` | ❌ | ❌ | Hardcoded mock, no backend |

### 4.2 Sidebar

| Element | Status | Fix Needed |
|---|---|---|
| Navigation items | ✅ | — |
| Tags (from API) | ✅ | Tags should be clickable to filter library |
| Item counts per nav entry | ❌ | Hardcoded — need API calls |
| "Blogs" source → links to `/share` | ❌ | Wrong route, no article plugin |
| Theme toggle | ❌ | Two themes defined in CSS but no toggle button anywhere |

### 4.3 API Client Layer

All API modules are implemented and correct. The only missing wire-up:

- `ChatPage`: must pass `context_filters: { tags, source_types }` in POST body
- `TodayPage` omnibox: when input is a question (not URL), should pre-fill the chat input and navigate with state

---

## 5. Full v2 Migration Checklist

The following is the complete ordered list of tasks to fully wire and complete the v2 migration:

### Phase 1 — Immediate bugs & regressions (1-2 days)

- [ ] **Fix Share token persistence**: add Alembic migration for `share_tokens` table, update `share.py` to read/write from DB
- [ ] **Wire ChatPage context filters**: read `selectedTags` and `selectedSources` state from context rail, pass as `context_filters` in `streamChat()` call
- [ ] **Wire Sidebar counts**: fetch `GET /api/knowledge?per_page=1` for total library count, `GET /api/tasks` filtered to active for inbox badge, `GET /api/digest/today` total for digest count
- [ ] **TodayPage omnibox chat redirect**: when user types a question (non-URL), navigate to `/chat` and pre-populate the input via React Router `state`
- [ ] **Fix Blogs source in Sidebar**: remove `/share` link from Sources section; add placeholder `/articles` route or hide until article plugin exists
- [ ] **Add theme toggle**: `localStorage`-persisted `data-theme` attribute toggle button (sun/moon icon) in sidebar footer or topbar

### Phase 2 — UX completeness (3-5 days)

- [ ] **LibraryPage pagination**: implement "Load more" or infinite scroll (current: fetches only first 50)
- [ ] **Sidebar tag filtering**: clicking a tag in the sidebar should navigate to `/library?tag=X` and pre-apply the filter
- [ ] **ChatPage context rail**: replace "narrow to a tag or source" placeholder with actual tag checkboxes and source_type toggles; wire to API
- [ ] **GraphPage force-directed layout**: replace `layoutNodes()` radial with a proper force simulation (D3-force or `@react-spring/core` physics); make SVG fill container responsively
- [ ] **DigestPage ingest/skip**: persist to `digest_actions` DB table, mark items as acted-on so they don't resurface
- [ ] **LibraryPage: tag click filter**: clicking a tag pill on a card should filter the library to that tag
- [ ] **Topbar settings icon**: add a settings gear icon linking to a `/settings` page (even if the page is minimal initially)

### Phase 3 — New features (1-2 weeks)

- [ ] **Article/Web plugin**: implement `backend/knowledge_sources/plugins/article/` using `trafilatura` for extraction + summarization pipeline; wire to `POST /api/sources/article`
- [ ] **Article ingestion UI**: add a new page `/articles` or extend TodayPage omnibox to handle article URLs (it already detects URLs, just needs routing to the correct plugin)
- [ ] **PDF plugin**: `pdfminer.six` or `pypdf` for extraction, same summarization pipeline
- [ ] **Vector embeddings**: generate embeddings on ingestion (using `text-embedding-3-small`), store in `Embedding` table, update `HybridRetriever` with RRF fusion
- [ ] **Digest personalization**: score items by cosine similarity against user's interaction history (Embedding + digest_actions)
- [ ] **Settings page**: `GET/PATCH /api/settings` endpoint + `/settings` frontend page for LLM keys, language defaults, digest schedule
- [ ] **Auth gate**: simple Bearer token or password middleware using `app_password` config already defined

### Phase 4 — Polish (ongoing)

- [ ] Reddit plugin (PRAW or scraping)
- [ ] Keyboard shortcuts (Cmd+K command palette)
- [ ] Mobile/responsive CSS breakpoints
- [ ] Bulk import (OPML for feeds, XLSX for source lists)
- [ ] Email digest delivery (cron + SMTP)
- [ ] YouTube channel subscription ("follow this channel, auto-ingest new videos")

---

## 6. Frontend v2 UI/UX Analysis & Improvements

The v2 design system is genuinely strong — the Obsidian/Papyrus dual theme, the CSS variable architecture, the typography scale, and the component primitives are all production-quality. The problems are structural: the layouts are designed for a ~1400px viewport and don't adapt either wider or narrower.

### 6.1 Screen Real Estate — the core problem

The app renders inside a 240px sidebar + `1fr` main column layout. The main column then constrains content to `max-width: 920px` (narrow pages) or `max-width: 1200px` (wide pages). On a 1920px monitor, this means ~360px of dead whitespace on each side of every page. On a 2560px monitor it's even more extreme.

**Specific offenders**:

- `LibraryPage` grid: hardcoded `repeat(3, 1fr)` — on 1440px+ this should be 4-5 columns
- `GraphPage` SVG: fixed `W=900, H=520` viewport inside `layoutNodes()` — completely ignores container size
- `LibraryItemPage`: `maxWidth: 860px` centered — wastes ~500px on wide screens that could show a metadata sidebar
- `ChatPage`: message content spans full width of the chat column — very long lines at ≥1200px, poor readability
- `TodayPage`: single-column narrow layout that could be a dashboard with a two-column split

**Fixes**:

```css
/* Library grid — responsive columns */
.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 18px;
}

/* Chat messages — constrain reading width */
.chat-messages {
  max-width: 780px;
  margin: 0 auto;
  width: 100%;
}

/* Graph — fill container */
.graph-svg {
  width: 100%;
  height: 100%;
  viewBox: "0 0 100 100";  /* Use % coordinates, not px */
}
```

For `LibraryItemPage`, consider a two-column layout at ≥1200px: left 2/3 for content + transcript, right 1/3 for metadata panel (channel, views, duration, topics, tags).

### 6.2 GraphPage — non-interactive and not filling the screen

The current graph has three problems: (1) fixed 900×520 px canvas regardless of window size; (2) static radial layout — nodes don't move, repel, or respond to hover; (3) no zoom/pan.

**What it should be**:
- SVG with `viewBox="0 0 W H"` where W/H come from a `ResizeObserver` on the container div
- Force-directed layout using `d3-force` (lightweight, ~30KB) so nodes cluster by shared tags naturally
- Click on a node → navigate to `/library/:id` or filter library
- Zoom/pan via `d3-zoom` or CSS `transform`
- Hover tooltip with item title, channel, tags

**Minimal implementation** — use `@antv/g6` or `react-force-graph-2d` which handle all of this in ~50 lines.

### 6.3 ChatPage — context rail is dead weight

The left context rail in ChatPage shows "All sources / narrow to a tag or source" but is entirely non-functional. It occupies 240px of every chat session for no value.

**Two options**: (1) make it functional (tag checkboxes + source type toggles that actually wire to the API), or (2) collapse it into a floating filter toolbar above the chat input. Option 1 is correct — the rail has the right information architecture, just needs real controls.

**Functional context rail**:
```tsx
// Replace the placeholder with:
<div className="ctx-section-label">Filter sources</div>
{(['youtube', 'article', 'reddit'] as const).map(type => (
  <label key={type} className="ctx-toggle">
    <input
      type="checkbox"
      checked={selectedSources.includes(type)}
      onChange={() => toggleSource(type)}
    />
    {type}
  </label>
))}

<div className="ctx-section-label">Filter tags</div>
{tags.map(t => (
  <label key={t.name} className="ctx-toggle">
    <input
      type="checkbox"
      checked={selectedTags.includes(t.name)}
      onChange={() => toggleTag(t.name)}
    />
    {t.name} <span className="count">{t.count}</span>
  </label>
))}
```
Then pass `{ source_types: selectedSources, tags: selectedTags }` in the chat POST body.

### 6.4 TodayPage — missed dashboard opportunity

Today is a narrow single-column page. The omnibox is great; the queue cards are functional. But it doesn't leverage the full width for a quick-glance dashboard.

**Proposed layout at ≥1200px** (two-column split):
- **Left column (60%)**: omnibox + active task queue
- **Right column (40%)**: mini-digest (top 3 recommended items from `/api/digest/today`) + quick stats (total items, items this week, tags)

This turns "Today" into a real home screen — the kind you'd want to open first thing.

### 6.5 Missing: Theme toggle

The CSS defines both `obsidian` and `papyrus` themes perfectly. But there's no button anywhere to switch between them. The sidebar footer has a user avatar placeholder — this is the natural place for a theme toggle.

```tsx
// In Sidebar footer
<button
  className="btn ghost"
  onClick={() => {
    const next = document.documentElement.dataset.theme === 'obsidian' ? 'papyrus' : 'obsidian'
    document.documentElement.dataset.theme = next
    localStorage.setItem('merlin-theme', next)
  }}
>
  {theme === 'obsidian' ? <Icons.sun /> : <Icons.moon />}
</button>
```

Initialize from `localStorage.getItem('merlin-theme') ?? 'obsidian'` in `main.tsx`.

### 6.6 Missing: Command palette (Cmd+K)

A personal knowledge tool is used by power users who don't want to mouse around. A Cmd+K palette that searches the library and navigates to pages would make the app feel professional. Libraries like `cmdk` (by Radix) add this in ~100 lines.

**Suggested commands**:
- Search knowledge items (live API search)
- Navigate to Today / Library / Chat / Graph / Digest
- Ingest YouTube URL (pre-fill the omnibox)
- Open recent items

### 6.7 Missing: Keyboard shortcuts

| Action | Shortcut |
|---|---|
| Open command palette | `Cmd+K` |
| Focus omnibox (Today) | `/` |
| New chat | `Cmd+N` on ChatPage |
| Back to library | `Escape` on LibraryItemPage |
| Submit chat | `Enter` (already works) |

### 6.8 LibraryItemPage — transcript viewer needs work

The transcript (`raw_content`) is shown via a toggle ("Show full transcript") that dumps the entire text in a monospace block. For a 3-hour video this is thousands of words with no navigation.

**Better approach**:
- Parse `topics` (which has `{ "Topic": "00:12:34" }`) into a clickable timeline navigation in a sticky sidebar
- Clicking a topic title scrolls to that section of the transcript
- Deep-link to YouTube with `?t=SECONDS` so users can jump to the source

### 6.9 InboxPage — task cards lack visual hierarchy

The inbox shows tasks as simple rows. There's no visual distinction between `queued`, `processing`, and `failed` states beyond a status badge. For a processing item showing 40% progress, the linear progress bar is good, but the card doesn't show what's being processed (title/thumbnail).

**Improvement**: once a task has fetched metadata (title available early in the pipeline), show it in the task card with the thumbnail. This makes the inbox feel alive rather than showing opaque UUIDs.

### 6.10 Mobile / Responsive

There are zero responsive CSS breakpoints. The 240px sidebar + 240px context rail (Chat) means the main content area collapses to a very small column on a 768px viewport. This is a personal tool and mobile is lower priority, but at minimum a "collapse sidebar" button at ≤900px would prevent breakage.

---

## 7. Enhancing Merlin with Karpathy's LLM Wiki

> Reference: `docs/karpathy_llm_wiki.md` and `docs/karpathy-llm-wiki-compatibility-analysis.md`

The compatibility analysis already in the repo is an excellent deep-dive. This section translates the architectural insight into concrete implementation ideas.

### 7.1 The Core Gap: Stateless RAG vs. Compounding Knowledge

Merlin today is a **stateless retriever**: every chat query does a fresh FTS5 search, returns the top-5 excerpts from raw summaries, and the LLM answers from scratch. The quality of the answer for "explain Transformers to me" is the same after you've ingested 1 video as after you've ingested 50 — it just has more excerpts to draw from.

Karpathy's insight is that an LLM agent should be compiling knowledge between sessions — synthesizing a `Transformer.md` concept page from those 50 videos, noting where they agree, where they contradict, what terminology evolved. Then the chat query retrieves the compiled page (84% fewer tokens) and answers from a grounded, pre-synthesized knowledge base that gets richer over time.

The bridge Merlin needs: a **post-ingestion synthesis job** that runs after each item is ingested and updates concept-level entities.

### 7.2 Idea: The Concept Synthesis Layer

**New DB table**:
```sql
CREATE TABLE concept_pages (
  id TEXT PRIMARY KEY,              -- uuid
  slug TEXT UNIQUE NOT NULL,        -- e.g. "transformer-architecture"
  title TEXT NOT NULL,              -- "Transformer Architecture"
  body TEXT,                        -- LLM-synthesized markdown
  source_item_ids JSON,             -- ["uuid1", "uuid2"] — contributing items
  last_synthesized_at DATETIME,
  synthesis_model TEXT,             -- which LLM wrote it
  has_contradictions BOOLEAN DEFAULT 0,
  created_at DATETIME,
  updated_at DATETIME
);
```

**New background job** (`ConceptSynthesizer`):

After a `KnowledgeItem` is marked `completed`:

1. **Concept extraction**: Ask the LLM to extract concepts from the new item's summary + topics: `["Transformer", "Self-Attention", "Positional Encoding", ...]`

2. **Existing concept lookup**: FTS5 search to find existing concept pages that overlap with the extracted concepts.

3. **Synthesis**: For new concepts, create a concept page. For existing concepts, re-synthesize by passing the existing page body + the new item's summary + ask the LLM to: (a) update the page with new information, (b) flag any contradictions with `[!contradiction]` callout blocks.

4. **Link graph**: Add `concept_page_id → knowledge_item_id` edges. The graph becomes `concept → item` rather than `tag → item`.

**New chat retrieval path**: `HybridRetriever` gets a second retrieval path:
- Path A (current): FTS5 raw item summaries → top-5 excerpts
- Path B (new): FTS5 concept pages → top-3 synthesized concept summaries
- Merge with Reciprocal Rank Fusion, serve both as context

### 7.3 Idea: Contradiction Detection

When the synthesizer finds that a new item contradicts an existing concept page, it:
1. Sets `concept_pages.has_contradictions = True`
2. Adds a `[!contradiction]` block to the page body: `> **Contradicts**: [Item A] says X, [Item B] says Y`
3. Surfaces contradictions in the UI: Library filter for "Has contradictions" + orange badge on the knowledge graph node

This turns Merlin from a passive archive into an active epistemic tool — you can see where your sources disagree.

### 7.4 Idea: Wiki Linting

A periodic background job (or user-triggered button) that:
- Finds concept pages with no source items (orphaned)
- Finds concept pages not updated in 90+ days (potentially stale)
- Finds items in the library with no concept page yet (unlinked)
- Reports these to a `/lint` page or digest section: "Your knowledge base has 3 unlinked items and 1 potential contradiction worth reviewing"

The "lint wiki" concept from Karpathy's community maps directly to a `/api/knowledge/lint` endpoint.

### 7.5 Idea: Semantic Graph (replace tag graph)

Current graph: `Item A → tag:ai → Item B` (two-hop, user-assigned labels)

Karpathy graph: `Item A → Concept:Transformer → Item B → Concept:Self-Attention → Concept:Attention` (n-hop, LLM-extracted semantic concepts)

With the `concept_pages` table, the graph becomes genuinely interesting:
- **Green nodes**: concept pages (sized by number of contributing sources)
- **Blue nodes**: knowledge items (smaller)
- **Edges**: item → concept (contributes to), concept → concept (is related to, shares items)
- Clicking a concept node opens the synthesized concept page
- Filtering by concept gives you "show me everything I've learned about Transformers"

### 7.6 Idea: Digest as "What's Changed in My Wiki"

Instead of "recently added items sorted by date," the digest could surface:
1. Concept pages that were updated in the last 24 hours (new synthesis happened)
2. New contradictions detected
3. Concepts with the most new evidence since last visit
4. "You've ingested 5 items about LLMs this week — here's the synthesized update"

This is the digest that's actually worth checking every day.

### 7.7 Idea: Compounding Summary on LibraryItemPage

When viewing a YouTube video, the current page shows: video metadata + LLM summary + raw transcript.

With concept synthesis, it could also show: "**Related concepts in your library**: [Transformer Architecture] (3 videos), [RLHF] (2 videos)" — linking to the concept pages that this video contributed to. This shows the item's place in the bigger knowledge graph, not just its isolated summary.

### 7.8 Implementation Sequence

If building the Karpathy layer on top of Merlin, the order matters:

1. **First**: Generate embeddings on ingestion (populate `Embedding` table). This is a prerequisite for concept clustering.
2. **Second**: Build `ConceptExtractor` — simple LLM prompt that extracts a JSON list of concepts from a summary. Run this as a post-ingestion hook.
3. **Third**: Create the `concept_pages` table and `ConceptSynthesizer` background job.
4. **Fourth**: Add concept-page retrieval path to `HybridRetriever`.
5. **Fifth**: Update `GraphPage` to show concept nodes (much richer graph).
6. **Sixth**: Add contradiction detection + linting endpoint.
7. **Seventh**: Update `DigestPage` to show concept-level changes.

Each step is independently valuable and doesn't block the next.

### 7.9 What Merlin Already Has That Karpathy Doesn't

Karpathy's setup is a CLI + local markdown files with manual ingestion. Merlin already outperforms it in:

- **Async background ingestion** with progress tracking — no blocking terminal commands
- **Audio fallback** — if YouTube has no subtitles, Groq Whisper transcribes the audio
- **Rich metadata** — views, subscriber counts, duration, detected language
- **Web UI** — shareable links, tag editing, filter/search UI
- **Multi-source ready** — plugin architecture waiting for article/PDF/Reddit

The Karpathy layer (concept synthesis, compounding knowledge) is the only thing Merlin is missing to surpass the state of the art in personal knowledge tooling.

---

## 8. Phased Roadmap

### Phase 1 — Wire & Fix (1 week)
High-impact, no new backend features required.

- Fix Share token persistence (DB migration)
- Wire ChatPage context filters to API
- Wire Sidebar counts to API
- Add theme toggle
- Fix TodayPage chat redirect with pre-filled query
- Fix Sidebar Blogs link

### Phase 2 — UX Overhaul (2 weeks)
Make the UI genuinely use the screen.

- Responsive library grid (`auto-fill minmax`)
- GraphPage: force-directed layout + full-screen SVG
- ChatPage: functional context rail (tag/source checkboxes)
- TodayPage: two-column dashboard layout
- LibraryItemPage: two-column layout (content + metadata panel with topic navigation)
- Command palette (Cmd+K) with `cmdk`
- InboxPage: show metadata (title/thumbnail) in task cards

### Phase 3 — New Source Plugins (3 weeks)
Grow the library beyond YouTube.

- Article plugin (trafilatura-based web scraping + summarization)
- Article ingestion UI (extend omnibox, add `/articles` page)
- PDF plugin (pdfminer/pypdf extraction)
- Update Source Pills and LibraryItemPage for new types

### Phase 4 — Smarter Retrieval (2 weeks)
Make chat answers better as the library grows.

- Embedding generation on ingestion (text-embedding-3-small)
- Vector retrieval in HybridRetriever (RRF fusion with FTS5)
- Digest personalization (cosine similarity to interaction history)

### Phase 5 — Karpathy Layer (4-6 weeks)
The compounding knowledge brain.

- ConceptExtractor post-ingestion hook
- `concept_pages` DB table + migration
- ConceptSynthesizer background job
- Contradiction detection + `[!contradiction]` blocks
- Concept-page retrieval in HybridRetriever
- GraphPage: concept nodes (semantic graph)
- DigestPage: wiki-change surfacing
- Wiki Linting endpoint + UI

### Phase 6 — Production Hardening (ongoing)
- Auth layer (password gate middleware)
- Settings API + Settings page
- Reddit plugin
- Keyboard shortcuts
- Responsive CSS (mobile-friendly sidebar collapse)
- YouTube channel subscriptions (follow + auto-ingest)
- Email digest delivery

---

*Generated by analysis of /home/prem/merlin codebase on 2026-04-26. All file paths, API routes, and feature statuses verified against current code.*
