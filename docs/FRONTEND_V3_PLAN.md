# Frontend v3 — Design & Build Plan

> Status: **Tier 0 shipped & cut over** (last reviewed 2026-06-19). v3 (FastAPI
> `api/` + React `web/`) is now the **only** UI; the Streamlit app has since been
> removed entirely. Tier 1 is mostly done but pivoted (the Inbox
> became the **Feed**); **Tier 2 — semantic search + the Karpathy wiki layer, the
> stated moat — has not started.** See **§0.5 Current status** for the honest
> map of what's built vs. what this plan originally proposed. The tier/build-order
> sections below are annotated with ✅/🟡/❌ but otherwise preserve the original intent.

## 0. Context — what this has to serve

Merlin is a **daily-driver personal knowledge vault** for a senior ML engineer
who doesn't write frontend. Reading the docs (`SESSION_NOTES.md`,
`MERLIN_FULL_ANALYSIS.md`), the frontend serves two things:

1. **Ingest → summarize → browse → chat** over content (YouTube today; articles,
   PDFs, podcasts later — the data model is already source-agnostic).
2. **A compounding "second brain"** — the *Karpathy LLM wiki layer*: per-item
   summaries get synthesized into cross-source `[[wikilinked]]` pages the LLM
   maintains on every ingest. This is the differentiator, not yet built.

> Out of scope for the frontend: the **LoRA fine-tune** work
> (`LORA_FINETUNE_PLAN.md`, `scripts/export_training_data.py`) is a separate
> side project to run a local summarizer and bypass the API LLM — it has no v3
> UI surface.

### The one hard requirement

From the owner, verbatim intent: *"few working pretty features rather than a lot
of placeholders never connected like it was for v2."* v2 died of **112 files,
half-wired**. **v3's prime directive: every surface ships fully wired to a real
service, or it doesn't ship.** Nav grows as features become real — never ahead.

### What we learned the hard way (don't repeat)

- **Streamlit has a polish ceiling.** Injected CSS via `st.html` is stripped by
  DOMPurify; native widgets top out at "clean internal tool." (See `SESSION_NOTES.md`.)
- **AppTest ≠ pixels.** Verify appearance in a real browser.
- **v2's pain wasn't React — it was placeholders + two-process contract drift.**
  v3 fixes that with vertical slices + a generated typed API client.
- **Screen real estate**: must fill a 32" 4K display, not left-hug (a specific
  v2 failure). Content max-widths, real layout.

---

## 0.5 Current status (reviewed 2026-06-19)

The prime directive held: everything that shipped is fully wired — no
placeholders. But momentum went into **deepening Tier 0/1 consumption** (Feed,
per-item chat, search/summary quality) rather than crossing into **Tier 2, which
this plan calls "the soul / the moat."** That work is still entirely unbuilt.

**Tier status:**

| Tier | State |
|---|---|
| **Tier 0** (Today, Library, Reader, Add-source, Chat) | ✅ **Done & cut over.** v3 is the daily driver. |
| **Tier 1** (Inbox/Digest, Insights) | 🟡 **Insights ✅. Inbox pivoted → Feed** (see below). |
| **Tier 2** (semantic search, wiki layer, more sources) | ❌ **Not started.** `embeddings` still unused; no `wiki_updater`/graph; YouTube remains the only plugin. |

**The Inbox → Feed pivot.** The Tier-1 triage Inbox was built, then **retired and
replaced by the Feed** — a swipe-to-read queue of *unread* items. New state on
`knowledge_items`: `read_at` (NULL ⇔ unread) + `saved_at` (★), via migration
`003`. The old `digest_actions` table, `api/routers/inbox.py`, and
`merlin/services/digest.py` still exist but are **orphaned** (safe to drop). Plan:
`docs/FRONTEND_V3_FEED_PLAN.md`.

**Built on top of Tier 0, not in the original plan** (scope that accreted —
mostly YouTube/consumption depth, all core-level, no new tier):

- **Description grounding** — `youtube_metadata.description` (migration `004`);
  summaries *and* chat are grounded in the video description.
- **Per-item chat** — `chat.answer()` takes `filters.item_id` to chat against one
  item's full transcript (no FTS, no citations); surfaced as a Reader tab.
- **Self-heal on re-summarize** — detects YouTube metadata fields old items lack
  and does a cheap metadata-only refetch to backfill them.
- **Library search overhaul** — relevance ranking, fuzzy fallback, transcript
  toggle. **Summary-prompt revamp** — dropped the "medium" tier (short/long only;
  legacy values coerced). **Language handling** — detect original spoken language;
  summarize in the languages the user understands.
- **UI polish** (consistent with §5, just undocumented): ⌘K command palette,
  `g`-prefix keyboard shortcuts, mobile drawer/responsive layout, persisted
  density + grid/list prefs, optimistic mutations.

**Next push** is Tier 2 — the differentiator (semantic search + the compounding
`[[wikilinked]]` wiki). A new source plugin (Reddit) is *planned* but unbuilt
(`docs/REDDIT_SOURCE_PLAN.md`).

---

## 1. Stack

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| Build/framework | **Vite + React + TypeScript** | Single-user localhost/NAS app needs no SSR/SEO/edge. Next.js App Router + RSC is the "bleeding edge / too complicated" to avoid. Vite SPA = fewest moving parts, instant HMR. |
| Styling + components | **Tailwind v4 + shadcn/ui** | You **own** the component source (copy-paste, no version lock), Radix-based (accessible), best-documented combo. This is the "easy/self-docs like shadcn" the owner named. |
| Server state | **TanStack Query** | Declarative caching, background refetch, task-progress polling. Kills manual-fetch spaghetti. |
| Routing | **React Router v7** | Most popular, boring-in-a-good-way. (Not TanStack Router — newer than the "not bleeding edge" bar.) |
| Client UI state | **Zustand** | Only for palette-open, filters, density. No Redux ceremony. |
| Graph | **React Flow** | Fixes the "graph is non-interactive" critique directly. Pan/zoom/click, well-documented. |
| Charts | **Recharts** | Simple, popular; ports the existing Plotly Insights cleanly. |
| Markdown | **react-markdown** + remark-gfm | Summaries + wiki pages; `[[wikilinks]]` rendered as clickable nodes. |
| Command palette | **cmdk** | The Cmd-K palette v2 lacked; shadcn wraps it natively. |
| Animation | **motion** (Framer) | Restrained micro-interactions only. |
| Icons | **lucide-react** | Pairs with shadcn. |
| Streaming | native `fetch` + `ReadableStream` (SSE) | Chat tokens + task progress over SSE from FastAPI. |

Backend stays **FastAPI** — thin, a 1:1 HTTP skin over the already-clean
`merlin.services`. The core library (`merlin/`) is **not modified**.

---

## 2. Architecture

```
merlin/            # core lib — UNTOUCHED (services already return plain dicts)
api/               # NEW: FastAPI, thin
  main.py          #   app, CORS (dev), static-file mount of built web/
  deps.py
  sse.py           #   chat token stream + task-progress stream
  routers/
    library.py  ingest.py  chat.py  insights.py  inbox.py
web/               # NEW: Vite + React + TS + Tailwind + shadcn
  src/
    routes/        #   today, library, reader, chat, inbox, insights (+ later: graph, wiki)
    components/
      ui/          #   shadcn primitives (owned)
      <feature>/   #   item-card, citation-list, task-panel, omnibox, command-palette
    lib/api/       #   GENERATED typed client + thin wrappers
    hooks/         #   useItems, useItem, useIngest, useChatStream, useTaskProgress
    store/         #   zustand (palette, filters, density)
  index.html  vite.config.ts  tailwind.config / @theme
docker-compose.yml # services: api (uvicorn, serves /api/* + built SPA) [+ db at Tier 2]
```

> **Historical note:** Streamlit was first moved to `streamlit/` as an archived
> "engine room," then removed entirely once v3 reached parity. React (`web/`) is
> now the only UI; `merlin/` was never modified by any of this.

### The single practice that prevents v2's contract drift

Generate the TS client from FastAPI's OpenAPI schema (**`openapi-typescript`**).
Frontend types regenerate from the backend; they can't silently diverge. This is
what makes FastAPI + React pleasant instead of a sync chore.

### Division of labor (fits the owner)

- **Frontend is the assistant's** — shadcn keeps it readable; owner can nudge.
- **`api/` is the owner's** — pure Python, the language they live in. Capability
  grows in Python; polish grows in `web/`.

### Deploy

One container: uvicorn serves `/api/*` and the built static bundle. Dev: Vite
dev server proxies `/api` → uvicorn. No nginx needed for single-user.
DB stays **SQLite** for Tier 0–1; the Tier-2 vector/graph work is the trigger to
revisit **pgvector** (see the SQLite-vs-Postgres discussion: migrate on a
*capability* wall, not a reliability one).

---

## 3. API surface (maps 1:1 to existing services)

Everything in Tier 0 already exists in `merlin.services` — the router is glue.

| Method + path | Calls | Notes |
|---|---|---|
| `GET /api/items` | `library.list_items` | query: `search, source_type, status, tags[], sort, page, per_page` |
| `GET /api/items/{id}` | `library.get_item` | includes `raw_content` |
| `PATCH /api/items/{id}` | `library.update_item` | tags / title |
| `DELETE /api/items/{id}` | `library.delete_item` | |
| `POST /api/items/{id}/resummarize` | `ingest.resummarize` | returns `task_id` |
| `POST /api/items/{id}/clear-summary` | `library.clear_summary` | |
| `POST /api/ingest/youtube` | `ingest.submit_youtube` | dedups → resummarize when already present; returns `task_id` |
| `POST /api/items/{id}/retry` | `ingest.retry` | |
| `GET /api/tasks` / `GET /api/tasks/{id}` | `ingest.recent_tasks` / `get_task` | |
| `GET /api/tasks/{id}/stream` | (SSE) polls `get_task` | live progress |
| `POST /api/chat` | `chat.answer` | SSE token stream + citations payload |
| `GET /api/tags` | `library.list_tags` | |
| `GET /api/source-types` | `library.list_source_types` | nav source list |
| `GET /api/insights/*` | `library.{ingest_timeline,top_channels,status_counts,count_channels}` | charts |
| `GET /api/digest` / `POST /api/digest/{id}/action` | new thin svc over `digest_actions` + recent tasks | Tier 1 |

---

## 4. Feature tiers — each a complete vertical slice

> Annotated 2026-06-19: ✅ done · 🟡 partial/pivoted · ❌ not started.

### Tier 0 — ✅ DONE — a pretty, *complete* app from services that already exist

(Zero new backend logic ⇒ nothing can be a placeholder.)

1. ✅ **Today** — omnibox (paste URL → ingest, or type → chat), live stats,
   recently-added grid, **live ingest progress (SSE)** + a "Needs attention" strip.
2. ✅ **Library** — grid/list, FTS5 search, sort, tag filter, density, pagination
   (+ later: relevance ranking, fuzzy fallback, transcript-search toggle).
3. ✅ **Reader** — markdown summary, **timestamped topics → YouTube deep-links**,
   transcript, edit tags/title, **re-summarize**, retry, delete (+ later:
   per-item chat tab, clear-summary, prev/next nav).
4. ✅ **Add source** — language list + length picker + task tracking.
5. ✅ **Chat** — streaming RAG, citations, follow-ups, source/tag filters.

### Tier 1 — 🟡 mostly done, one pivot

6. 🟡 **Inbox / Digest → PIVOTED to the Feed.** The triage queue was built then
   retired; the **Feed** (swipe-to-read queue of unread items, `read_at`/`saved_at`
   state, migration `003`) replaced it. `digest_actions` + `inbox.py` + `digest.py`
   are now orphaned. Email digest never built. See `FRONTEND_V3_FEED_PLAN.md`.
7. ✅ **Insights** — Plotly charts ported to Recharts (timeline heatmap, top
   channels, status donut).

### Tier 2 — ❌ NOT STARTED — the soul (real backend work, the moat)

8. ❌ **Semantic search** — backfill the unused `embeddings` table (sqlite-vec or
   pgvector); hybrid retrieval → better chat *and* a meaningful graph. *(Table
   still empty/unused.)*
9. ❌ **Karpathy wiki layer** — `wiki_updater` on every ingest; `[[wikilinked]]`
   pages; **interactive React Flow graph**; backlinks; contradiction detection;
   "what changed in my wiki" digest. *(Nothing built; React Flow not yet a dep.)*
10. ❌ **More sources** — article/PDF/podcast plugins (model already
    source-agnostic). *(Reddit planned in `REDDIT_SOURCE_PLAN.md`, not built;
    YouTube still the only plugin.)*

---

## 5. Aesthetic direction

Lean into the v2 look the owner liked; make it fill the screen and feel alive.

- **Near-black canvas, one accent**, generous spacing, **monospace eyebrow
  labels** (`WORKSPACE`, `YOUTUBE`, timestamps) — the texture from the v2 shots.
- **Content max-widths** (reading column ~70ch) so it doesn't left-hug on 4K.
- **Polish lives in interaction, not decoration** (the apple_health lesson):
  skeleton loaders, optimistic tag edits, hover lifts, Cmd-K, keyboard shortcuts
  (`j/k`, `/` search, `g l` Library), toast on ingest-complete.
- shadcn neutral dark theme; thumbnail cards with duration badges; React Flow
  graph as the Tier-2 centerpiece.

---

## 6. Build order

| Step | What | Proves | Status |
|---|---|---|---|
| 1 | `api/` FastAPI: items list/get, ingest, SSE task progress | backend skin | ✅ |
| 2 | `openapi-typescript` → typed client | no contract drift | ✅ |
| 3 | `web/` scaffold: Vite+TS+Tailwind+shadcn+Router+Query; shell (sidebar + Cmd-K) | the chrome | ✅ |
| 4 | **Library + Reader, fully wired** | the whole pattern, end to end | ✅ |
| 5 | Today + Chat (SSE) | streaming + dashboard | ✅ |
| 6 | Add-source flow + task panel | ingest loop closed → **Tier 0 done, cut over** | ✅ **cut over** |
| 7 | ~~Inbox/Digest~~ → **Feed** + Insights | Tier 1 | 🟡 Insights ✅; Inbox pivoted to Feed |
| 8+ | Embeddings → wiki layer → graph → new sources | Tier 2 | ❌ **not started ← next push** |

**UI:** `web/` is the only UI as of **Tier-0 parity** (step 6, done); the Streamlit
app — first archived, then removed — is gone.

---

## 7. Resolved decisions & open questions

**Resolved:**
- **Accent**: keep the original red (`#ff4b4b`), built into a cohesive ramp on
  pure-neutral surfaces (see `FRONTEND_V3_DESIGN_SYSTEM.md`).
- **Migration**: build `api/` + `web/` in the **same repo** alongside the old
  Streamlit app, cut over at Tier-0 parity, then remove Streamlit.
- **End goal**: self-hosted on the **NAS**, used from devices over the web; the
  FastAPI server is the **only** DB client (browsers hit the server, not the DB),
  so multi-device access does **not** by itself require Postgres.

**DB strategy (see §8):**
- **Tier 0–1 → SQLite.** Reliable on the NAS (native Linux FS — the WAL data-loss
  was a *macOS Docker bind-mount* artifact, not a NAS issue). Dev on Mac uses a
  **local copy** of the DB file.
- **Tier 2 → Postgres (with pgvector), one instance per environment.** This is the
  capability wall (semantic search + graph) *and* the point where FTS5 gets
  rewritten anyway. Local Postgres container for dev, Postgres on the NAS for prod,
  wired by `DATABASE_URL`. **Do not** run SQLite over a network mount, and don't
  point dev directly at the prod DB — see §8.

**Open:**
- **Auth**: single-user / LAN today (none). Needed once exposed to the open web
  from devices off-LAN — add a simple auth layer (single password / reverse-proxy
  auth / Tailscale) before public exposure. The `share_tokens` table is a later
  scoped public-share feature.
- **Email digest** transport (Tier 1): SMTP creds vs. a provider.

## 8. Where the database should live (dev on Mac, prod on NAS)

The key fact: **SQLite is a local-file database, Postgres is a network server.**
That single distinction answers the "remote Postgres on the NAS?" question.

| You want… | Use |
|---|---|
| Dev and prod each with their **own** data | **SQLite** both sides (local file on Mac, file on NAS). Simplest. Copy the file when you want prod data locally. Offline-friendly. |
| Dev on Mac to hit the **same live data** as the NAS | A **network DB → Postgres on the NAS**. SQLite **cannot** do this safely (file locking over NFS/SMB is unreliable — same failure class as the macOS bind-mount). |
| Semantic search / knowledge graph (Tier 2) | **Postgres + pgvector** regardless. |

**Recommendation:**
- **Now (Tier 0–1):** SQLite. NAS prod = SQLite on local disk (fine on Linux).
  Dev = local SQLite copy. Lowest friction; ship the frontend.
- **At Tier 2:** move to **Postgres**, one instance per environment — a local
  Docker Postgres for dev (offline, isolated, zero risk to prod data) and Postgres
  on the NAS for prod, selected by `DATABASE_URL`. This gives full dev/prod parity
  without developing against live production data.
- **Avoid:** "remote Postgres on the NAS as the *dev* database." It couples dev to
  the network (no offline work, LAN-only latency) and means editing prod data while
  developing. A per-environment Postgres is the standard, safer setup.

> Net: a NAS Postgres makes sense **as the production DB at Tier 2** (and is the
> right tool if you ever truly need shared live data). It does **not** make sense
> as your everyday dev database. Until Tier 2, SQLite covers both.
