# Frontend v3 — Screen Specs

> Per-screen blueprint for v3. Companion to `FRONTEND_V3_PLAN.md` (stack/arch),
> `FRONTEND_V3_DESIGN_SYSTEM.md` (visual language), `FRONTEND_V3_PATTERNS.md`
> (data/interaction patterns). Wireframes are ASCII sketches, not pixel specs.
>
> **Rule for every screen:** it ships only when *all* of `loading / empty / error /
> ready` states are built and wired to a real endpoint. No placeholders.

## App shell (every route)

```
┌────────────┬───────────────────────────────────────────────────────────┐
│ ✦ Merlin   │  Today            ⌘K Search            [+ Add source]       │  ← topbar
│            ├───────────────────────────────────────────────────────────┤
│ WORKSPACE  │                                                            │
│ ▸ Today    │      < route content, centered max-w-[1400px] >            │
│ ▸ Library 803                                                           │
│ ▸ Inbox    │                                                            │
│ ▸ Chat     │                                                            │
│ ▸ Insights │                                                            │
│            │                                                            │
│ SOURCES    │                                                            │
│ ▸ YouTube 803                                                           │
│            │                                                            │
│ ─────────  │                                                            │
│ ◐ prem     │                                                            │
└────────────┴───────────────────────────────────────────────────────────┘
```

- Sidebar: `WORKSPACE` and `SOURCES` mono eyebrow groups; active item tinted
  (`--accent-subtle`) with a left accent bar; live counts from `/api/items` +
  `/api/source-types`.
- Topbar: breadcrumb/title left; Cmd-K search trigger center-right; `Add source`
  primary button right. Topbar is sticky.
- Nav grows **only as features become real** — Insights/Inbox appear when wired.

---

## 1. Today  `/`

The dashboard + entry point. Omnibox is the hero.

```
RECENTLY · THURSDAY, JUNE 12 · 803 SOURCES
Good evening.                                         ┌── LIBRARY ───────┐
                                                      │ 803  total       │
┌──────────────────────────────────────────┐ [Send]  │  4   this week   │
│ ✦ Paste a YouTube link, or ask Merlin…    │         └──────────────────┘
└──────────────────────────────────────────┘
accepts ▸ YOUTUBE · type a question to ask your library

INGESTING · 1 active                              View all →
● Downloading audio for transcription…  ▓▓▓▓▓░░░  62%

RECENTLY ADDED                                     View library →
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ [thumb] │ │ [thumb] │ │ [thumb] │ │ [thumb] │
│ title   │ │ title   │ │ title   │ │ title   │
│ ch · 1h │ │ ch · 1h │ │ ch · 2h │ │ ch · 2h │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

- **Omnibox**: classifier (`omnibox_route`-style) — URL → `POST /api/ingest/youtube`;
  text → navigate to Chat with the question prefilled. Enter submits.
- **Ingesting**: live `TaskRow`s via SSE (`/api/tasks/{id}/stream`); toast +
  refetch of recent on completion. Hidden when none active.
- **Recently added**: `list_items(sort=newest, per_page=8)`; cards → Reader.
- **Stat tiles**: total + this-week from items/insights.
- States: *loading* skeleton tiles + card row; *empty* (fresh vault) → big
  omnibox + "Ingest your first source"; *error* → inline retry on the failing block.

---

## 2. Library  `/library`

Browse everything. The workhorse grid.

```
Library                                                    803 sources
┌ Search ─────────────────┐  [Sort: Newest ▾]  [Grid|List]  [⌗ Cozy ▾]
│ ⌕ full-text…            │
└─────────────────────────┘
[ All ] [ YouTube ]                       (source-type chips)
tags: #ai ×  #python ×           (active tag filters, removable)

┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ [thumb] │ │ [thumb] │ │ ...     │ │ ...     │
│ 00:16:59│ │ 00:20:12│ │         │ │         │
│ Title…  │ │ Title…  │ │         │ │         │
│ ● ch·1h │ │ ● ch·1h │ │         │ │         │
│ snippet │ │ snippet │ │         │ │         │
│ #ai #ml │ │ #beef   │ │         │ │         │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
                       ‹ 1 2 3 … 66 ›
```

- Controls → query params on `GET /api/items` (`search, sort, source_type,
  tags[], page, per_page`). Search is debounced; FTS5 server-side.
- Grid/List toggle; density (Comfortable/Cozy/Compact) changes card min-width/gap.
- Card → Reader (`/library/:id`). Status dot per item.
- Pagination via server `total`. URL reflects state (shareable/back-button safe).
- States: *loading* card skeletons; *empty (no results)* → "No matches — clear
  filters"; *empty (no items)* → onboarding; *error* → retry.

---

## 3. Reader  `/library/:id`

The full reading + actions surface. Two columns on wide screens.

```
‹ Library                                   [↗ YouTube] [⟳ Re-summarize] [⋯]
─────────────────────────────────────────────────────────────────────────
Title of the video                          ┌── ON THIS PAGE ──────────┐
YOUTUBE · Channel · 16:59 · EN · 1,944 words │ • Overview      00:00    │
#ai #ml  + add tag                           │ • Key point 1   02:14    │
                                             │ • Key point 2   05:40    │
## Summary                                   │ • Takeaways     09:02    │
1. **Overview** …                            └──────────────────────────┘
   (markdown prose, ~70ch measure)
                                             [ Summary | Transcript ]
2. **Key points** …
```

- `GET /api/items/:id` (includes `raw_content`). Summary rendered as markdown.
- **Topics rail** = `topics`/`timestamps`; each entry deep-links to YouTube at
  the timestamp (`youtu.be/<id>?t=<sec>`) and scrolls the transcript tab.
- Tabs: **Summary** (default) / **Transcript** (raw_content, monospace-ish,
  searchable within).
- Actions: **Re-summarize** (`POST .../resummarize` → length popover → task +
  toast, optimistic "summarizing…" state), **Retry** (failed items), **Edit
  tags/title** (inline, optimistic `PATCH`), **Delete** (confirm dialog),
  **Open on YouTube**.
- States: *loading* title+prose skeleton; *failed item* → `ErrorState` showing
  `error_message` + Retry; *re-summarizing* → summary area shows progress.

---

## 4. Chat  `/chat`

Streaming RAG with citations. Single column, generous measure.

```
Chat                                          [filters: source ▾ tags ▾]
─────────────────────────────────────────────────────────────────────
you   What did the DJI video say about moats?
merlin DJI's edge comes from vertical integration… ▍(streaming)
       ┌ SOURCES ─────────────────────────────────────────────┐
       │ ① The Real Reason Nobody Can Beat DJI  · open →       │
       │ ② …                                                   │
       └───────────────────────────────────────────────────────┘
       ⟳ Regenerate   · follow-ups: [Why?] [Counterpoints?]
─────────────────────────────────────────────────────────────────────
┌ Ask your library… ────────────────────────────────────────┐ [Send]
└─────────────────────────────────────────────────────────────┘
```

- `POST /api/chat` (SSE): stream tokens into the assistant bubble; citations
  payload renders as `CitationCard`s after the stream (or as they resolve).
- History kept client-side, sent as `history` per turn.
- Filters → `filters.source_types` / `filters.tags`.
- Citations → open Reader. **Regenerate** re-runs last turn; **follow-ups** are
  suggested prompts.
- States: *idle* → empty state with example prompts (the "Ask your library"
  starters); *streaming* → token cursor + disabled input; *error* (LLM/network)
  → inline retry preserving the question; *no citations* → answer without rail.

---

## 5. Inbox / Digest  `/inbox`  *(Tier 1)*

The triage workshop — review recently ingested items, act, dismiss.

```
Inbox — the workshop                    0 processing · 19 done · 1 failed
                                                  [Retry failed] [Clear failed]
┌───────────────────────────┐ ┌───────────────────────────┐
│ ● FAILED                   │ │ Title…              Open → │
│ No subtitles — audio…      │ │ ready · added to Library  │
│ <error message>            │ │ [keep] [re-sum] [dismiss] │
│ [Retry]                    │ └───────────────────────────┘
└───────────────────────────┘
```

- Sources: recent `background_tasks` + `digest_actions`. Each card = an ingested
  item awaiting review.
- Actions: **keep** (→ stays in Library), **re-summarize**, **tag**, **dismiss**
  (`POST /api/digest/:id/action`); **Retry failed** for failed tasks.
- "Digest" framing: a daily roll-up of new items, optional **Send to email**.
- States: *loading* card skeletons; *empty* → "Inbox zero ✓"; *failed* cards
  styled with danger edge + message.

---

## 6. Insights  `/insights`  *(Tier 1)*

Port the existing Plotly charts to Recharts.

```
Insights                                   How your library has grown
┌ TOTAL ─┐ ┌ CHANNELS ─┐ ┌ MOST IN A DAY ─┐ ┌ FAILED ─┐
│  803   │ │   140     │ │     42         │ │   3     │
└────────┘ └───────────┘ └────────────────┘ └─────────┘
┌ Ingest activity (calendar heatmap) ─────────────────────────┐
│ ▢▢▣▣▢ … per-day intensity                                   │
└──────────────────────────────────────────────────────────────┘
┌ Top channels (hbar) ─────────┐ ┌ Status (donut) ────────────┐
└───────────────────────────────┘ └─────────────────────────────┘
```

- Data: `/api/insights/*` → `ingest_timeline`, `top_channels`, `status_counts`,
  `count_channels`. Charts honor the dark theme tokens.
- States: *loading* chart skeletons; *empty* (too few items) → "Ingest more to
  see trends".

---

## 7. Add source  (dialog, global)

Triggered by topbar button or Cmd-K. Modal `dialog`.

```
Add a source
┌ YouTube URL ──────────────────────────────────┐
└─────────────────────────────────────────────────┘
Summary length:  ( short )  medium   long
▾ Advanced — languages you understand: [EN ×][FR ×] +
                                          [ Cancel ]  [ Summarize ]
```

- `POST /api/ingest/youtube`; on submit → close dialog, show `TaskRow` on Today/
  Inbox, toast on completion.
- Dedup is server-side (already-ingested → re-summarize), surfaced as
  "Already in library — re-summarizing" in the toast.
- States: *submitting* → spinner on button; *validation error* → inline.

---

## Cross-screen: Command palette (Cmd-K)

A `cmdk` palette available everywhere — search items, jump to routes, run actions
(Add source, Re-summarize current, Toggle density). Full command list + keyboard
shortcuts in `FRONTEND_V3_PATTERNS.md`.

---

## Route → endpoint → states matrix

| Route | Primary endpoint(s) | Tier |
|---|---|---|
| `/` Today | `items?sort=newest`, `tasks/{id}/stream`, insights stats, `ingest/youtube` | 0 |
| `/library` | `items` (+ `tags`, `source-types`) | 0 |
| `/library/:id` Reader | `items/{id}`, `resummarize`, `retry`, `PATCH`, `DELETE` | 0 |
| `/chat` | `chat` (SSE), `tags`, `source-types` | 0 |
| Add-source dialog | `ingest/youtube`, `tasks/{id}/stream` | 0 |
| `/inbox` | `digest`, `digest/{id}/action`, `tasks` | 1 |
| `/insights` | `insights/*` | 1 |
| `/graph`, `/wiki` | (Tier 2 — embeddings + wiki layer) | 2 |

Every Tier-0 row uses an endpoint that wraps an **existing service** — so the
first cut is fully wired with no new backend logic.
