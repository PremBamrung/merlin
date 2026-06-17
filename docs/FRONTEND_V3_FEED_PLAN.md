# Frontend v3 — Feed (swipe-to-read) Plan

> Status: **proposal / reference** (no code yet). Adds a new consumption surface
> to the v3 React SPA (`web/`) and **retires the v2-heritage Inbox triage**.
> Pairs with `FRONTEND_V3_PLAN.md`, `FRONTEND_V3_API.md`, and the design system.

## 0. Why

The current consumption loop is high-friction: Library → click an item → read →
back → click the next → back. On mobile especially, that's a lot of navigation
to read a few summaries. The **Inbox tab** (a v2 carry-over: pending-review /
failed / processing sections backed by `digest_actions`) asks you to "keep or
dismiss" items you *haven't actually read* — triage disconnected from reading.

The **Feed** replaces that with a lean, swipeable queue of unread summaries.
Reading *is* the gesture: page through cards, each marked read as you leave it.
"Ingest now, read later" becomes a first-class habit — which matters more as
automatic ingestion of more source types (Reddit, articles, PDFs) lands and the
unread backlog grows.

**Prime directive carried over from v3:** ship one fully-wired surface, not a
placeholder. The Feed reads/writes real state through `merlin.services`.

## 1. Concept

A single queue of unread, completed items. One card per screen. The full
`Reader` route remains the "go deeper" escape hatch (transcript, all metadata,
re-summarize, chat). The Feed is deliberately **lean** — consume fast; if you
need more, open the Reader.

- **Queue** = `status = 'completed' AND read_at IS NULL`, **newest first**, no
  filters (filtering stays in Library).
- **Mark read on advance** — paging past a card marks the one you left as read.
- **Save** (★) is a separate axis from read — bookmark standouts to revisit.
- **No archive/dismiss** in the Feed — reading marks read; the item lives on in
  Library. The old keep/dismiss triage is gone.

## 2. The card (lean)

```
┌────────────────────┐
│ [▤ thumbnail]      │   thumbnail (when source has one)
│ ▶ Title here       │   source chip + title
│ Channel · 12m · Jun│   one muted meta line
│                    │
│ Summary body...    │   the summary — scrolls ↕ within the card
│ scroll ↕           │
│                    │
│ ★    ↗ full reader │   two actions only
│      ● 4 / 12      │   progress
└────────────────────┘
```

- **Header:** thumbnail (if the source provides one), source chip (▶ YouTube /
  Reddit / PDF …), title, and **one** muted meta line (e.g. `channel · duration
  · date`). Everything else lives in the Reader.
- **Body:** the summary (markdown), vertically scrollable. Reuse the Reader's
  summary renderer so formatting/deep-links are consistent.
- **Actions:** ★ **Save** (toggle) and ↗ **Open full reader**. Nothing else.
- **Progress:** `n / total` dot indicator.

## 3. Interaction model

Within a card you **scroll vertically** to read. Between cards you **page
horizontally** — this avoids colliding with in-card scroll and matches the
owner's instinct ("swap left/right or click").

| | Mobile | Desktop |
|---|---|---|
| Next / prev card | swipe ← / → (drag-to-page) | `←` `→` keys + on-card click-zones / ‹ › buttons |
| Read the summary | scroll ↕ within the card | scroll ↕ / trackpad |
| Save | tap ★ | click ★ / `s` key |
| Open full reader | tap ↗ | click ↗ / `Enter` |
| Undo last "read" | tap **Undo** in toast | click **Undo** / `u` |

**Mark-read semantics:** leaving a card (advancing to the next) sets `read_at`.
Safety net: a brief **"Marked read — Undo"** toast, and paging *back* to a read
card shows a one-tap **"Mark unread."**

**Empty state:** when the queue is drained, a calm "You're all caught up" with a
count of what you read this session and a link to Library / Ingest.

## 4. Responsive design — mobile *and* desktop

The Feed is the most mobile-critical surface in the app, but must also feel
right on the 32" 4K desktop the rest of v3 targets. One component, two
well-tuned layouts via Tailwind breakpoints (the `md` 768px breakpoint already
used by `AppShell`).

**Mobile (< `md`)**
- Card fills the viewport (full-bleed within the existing slide-in-drawer shell).
- Primary nav is touch: **horizontal swipe** to page (framer-motion `drag="x"`
  with snap + velocity threshold; a partial drag that doesn't pass threshold
  springs back).
- Large touch targets for ★ and ↗ (≥44px); actions pinned to a bottom bar within
  thumb reach.
- Respect safe-area insets (notch / home indicator). Body scroll locked to the
  card so the page itself doesn't bounce.
- Progress dots compact; meta line truncates with ellipsis.

**Desktop (≥ `md`)**
- Card centered with a comfortable **max reading width** (≈640–720px) on the
  near-black canvas — do **not** stretch the summary edge-to-edge (a known v2
  failure). The wide canvas frames the card rather than filling it.
- Keyboard-first: `←/→` page, `s` save, `Enter` open reader, `u` undo. Show a
  subtle hint on first visit.
- Optional click-zones (left third = prev, right third = next) plus visible
  ‹ › affordances on hover.
- Same framer-motion paging animation; drag works with a mouse too but keyboard
  is the expected path.

**Shared**
- Honor `prefers-reduced-motion`: swap the slide animation for an instant/cross-
  fade transition.
- Same data, same component, same state — only layout/affordances branch on
  breakpoint. No separate mobile route.

## 5. Data model

One **hand-written** Alembic migration (autogenerate is unreliable for this repo;
see CLAUDE.md). Two nullable timestamps on `knowledge_items`:

- `read_at` — `DATETIME NULL`. Unread ⇔ `read_at IS NULL`. Timestamp (not a
  bool) so we keep "when read" for free.
- `saved_at` — `DATETIME NULL`. The ★ flag; timestamp doubles as save order.

No FTS/trigger changes (these columns aren't searched). `digest_actions` is left
in place but orphaned (drop in a later cleanup pass).

## 6. Backend (`merlin/` + `api/`) — thin, arrow intact

`merlin/` must not import FastAPI; routers call **one** service fn and serialise.

**Services (`merlin/services/`)**
- `library.list_items`: add `read: bool | None` and `saved: bool | None` filters
  (None = no filter). `serialize_item` exposes `read_at` / `saved_at`.
- New mutators: `mark_read(item_id)` / `mark_unread(item_id)`,
  `set_saved(item_id)` / `unset_saved(item_id)`.
- Optional `feed.py` for the queue + unread count, or just reuse `list_items`
  with `read=False, sort="newest"` and a `count_unread()` helper.
- `digest.py`: keep the **failed-ingest** functions (retry/clear); remove the
  pending-review pieces.

**API (`api/`)**
- `GET /api/items`: add `read` and `saved` query params (passthrough to service).
- `POST /api/items/{id}/read` and `/unread`; `POST /api/items/{id}/save` and
  `/unsave`. 404 → `not_found` per the existing error envelope.
- Update `api/schemas.py`; regenerate the TS client from `/openapi.json`.
- Tests in `tests/backend/`: real router → service → temp-SQLite (real
  migrations), asserting unread filter + mark-read/save round-trips.

## 7. Frontend (`web/`)

- **New route `/feed`** in the nav slot freed by Inbox. `Today` stays the
  landing page. (Optionally a count badge on the Feed nav item.)
- Add **framer-motion** (drag + transitions in one dep) — preferred over
  `@use-gesture` + react-spring.
- **TanStack Query**: infinite query for the unread queue; **optimistic**
  `mark_read` mutation (swipe feels instant, rolls back on error); `save`
  mutation; invalidate Library/Today counts on change.
- **Undo** via a toast that calls `mark_unread`.
- Reuse the Reader's summary/markdown renderer for the card body.
- **Library:** add a **Saved** filter/toggle (no new tab) wired to `saved=true`.
- **Today:** add a small **"Needs attention"** strip surfacing failed ingests
  (retry/clear), inheriting the useful half of the old Inbox. Optionally a
  "Start reading — N unread" entry point into the Feed.
- **Remove** the `/inbox` route and the pending-review components.

## 8. Build order (vertical slices)

1. **Data + API.** `read_at` / `saved_at` migration; service filters + mutators;
   endpoints; backend tests. No UI yet — verifiable via tests/`/docs`.
2. **Feed MVP.** `/feed` route, card, horizontal paging, mark-read-on-advance,
   progress, empty state. Desktop keyboard + mobile swipe from day one.
3. **Polish + Save.** ★ save + optimistic mutations, undo toast, reduced-motion,
   safe-area insets, Saved filter in Library.
4. **Inbox retirement.** Move failed-ingest UI to Today; delete `/inbox` +
   pending-review service code; swap nav.

## 9. Decisions (locked) & open items

**Locked (this planning pass):**
- Read state = `read_at` column (not reused `digest_actions`).
- Mark read **on advancing past** a card; Undo toast + re-mark-unread on revisit.
- **Horizontal** paging; vertical scroll within card.
- Queue **newest first**, **no filters**.
- Dedicated **saved** flag (`saved_at`); Saved browsed via a **Library filter**.
- Card is **lean**: thumbnail + source chip + title + one meta line + summary;
  actions = ★ Save and ↗ Open full reader only.
- Feed takes the **Inbox nav slot**; **Today stays home**.
- Inbox triage retired; **failed ingests move to Today**.

**Open / deferred:**
- `digest_actions` table left orphaned now; drop in a later cleanup.
- Re-summarizing/processing items never enter the Feed (only `completed`).
- Newest-vs-oldest toggle could be added later if backlog reading needs it.
- Saved gets a dedicated tab later only if the Library filter proves insufficient.
