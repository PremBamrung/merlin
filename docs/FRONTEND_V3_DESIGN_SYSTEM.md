# Frontend v3 — Design System

> The visual language for v3. Companion to `FRONTEND_V3_PLAN.md` (stack/arch) and
> `FRONTEND_V3_SCREENS.md` (per-screen specs). Goal: a dark, calm, *expensive*-
> feeling vault where polish lives in **interaction and restraint**, not decoration.

## 1. Principles

1. **Dark-first, near-black canvas.** One surface family, one accent. No gradients-
   for-decoration, no drop shadows as ornament.
2. **Type and space do the work.** Hierarchy comes from size/weight/spacing and the
   monospace eyebrow treatment — not boxes and dividers everywhere.
3. **Restraint over flourish.** Motion is feedback, not entertainment (≤200ms).
4. **Every state is designed** — loading, empty, error, and partial are first-class,
   not afterthoughts. (This is how a slice stays "no placeholder".)
5. **Content has a measure.** Reading columns are capped (~70ch); the app fills a
   4K screen with intent, never left-hugging raw full-width text.

## 2. Color tokens

Defined as CSS variables (Tailwind v4 `@theme`) so shadcn components inherit them.
Values are starting points — tune in-browser, not in AppTest.

```
/* Surfaces (near-black, layered by elevation) */
--bg            #0a0a0b   /* app canvas */
--surface       #111113   /* cards, panels */
--surface-2     #18181b   /* raised / hover */
--border        #232327   /* hairlines */
--border-strong #2e2e33   /* focus rings, active edges */

/* Text */
--fg            #ededef   /* primary */
--fg-muted      #a1a1aa   /* secondary / captions */
--fg-subtle     #6b6b73   /* eyebrows, metadata, placeholders */

/* Accent — anchored on Streamlit's red (#ff4b4b), built into a small ramp.
   Red is the ONLY chroma in the chrome; neutral surfaces let it pop. */
--accent        #ff4b4b   /* brand red — primary buttons, active nav, links, focus */
--accent-hover  #ff6363   /* hover */
--accent-active #e23b3b   /* pressed */
--accent-fg     #ffffff   /* text/icon on a red fill (passes contrast on #ff4b4b) */
--accent-subtle #2a1416   /* low-chroma red-tinted surface: selected row, badge bg */
--accent-border #4d2122   /* red-tinted hairline: selected/active edges */
--accent-ring   rgba(255,75,75,0.45)  /* focus glow */

/* Semantic — chosen to coexist with a red brand (greens/amber/blue carry meaning
   without competing). Success/warning/info are the only non-red signals. */
--success       #30a46c   /* completed */
--warning       #f5a524   /* pending */
--info          #5b9df9   /* processing */
```

Status → treatment (cards, task rows, badges):
`completed → success`, `processing → info`, `queued → fg-subtle`,
`pending → warning`, **`failed → --accent` (red) + a `⛔ FAILED` mono eyebrow**.

> Because the brand accent *is* red, failures don't get a second red — they reuse
> `--accent` and are disambiguated by the status dot + the `FAILED` eyebrow + the
> error message. Don't introduce a competing danger-red. Keep surfaces pure
> neutral so the single red reads as intentional, not noisy.

## 3. Typography

Two families. A clean sans for everything; a mono for the "vault instrument" texture.

```
--font-sans  : "Inter", system-ui, sans-serif;   /* or Geist */
--font-mono  : "JetBrains Mono", ui-monospace, monospace;  /* or Geist Mono */
```

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `display`  | 30 / 36 | 600 | page hero ("Good evening") |
| `h1`       | 24 / 32 | 600 | screen titles |
| `h2`       | 18 / 26 | 600 | section heads, card titles |
| `body`     | 14 / 22 | 400 | default |
| `body-lg`  | 16 / 26 | 400 | reader prose |
| `caption`  | 13 / 18 | 400 | metadata, captions |
| `eyebrow`  | 11 / 16 | 500 | **mono, uppercase, +0.08em tracking**, `--fg-subtle` |

**Eyebrow** is the signature element — `WORKSPACE`, `YOUTUBE`, `RECENTLY ADDED`,
timestamps, counts. Mono + uppercase + letter-spacing. Use it for section labels
and metadata; never for body content.

Reader prose: `body-lg`, max-width ~70ch, generous paragraph spacing, markdown
via `react-markdown` + `remark-gfm`.

## 4. Spacing, radius, layout

- **Spacing scale** (Tailwind default 4px base): use `2,3,4,6,8,12,16,24` steps.
  Default gutter between cards `16` (1rem); section vertical rhythm `24–32`.
- **Radius**: `--radius: 10px` (cards/inputs), `6px` (badges/buttons-sm),
  `full` (avatars, pills). One consistent family.
- **Borders**: 1px hairline `--border`; hover lifts to `--surface-2` + `--border`.
  Avoid shadows except a single soft one on popovers/dialogs/command palette.
- **App layout**: fixed left sidebar (≈240px) + main column. Main content uses a
  centered max-width container (`max-w-[1400px]`) so 4K doesn't sprawl; reader
  and chat narrow further to their measure.
- **Grid**: Library cards in a responsive grid (`minmax(280px, 1fr)`), density
  control swaps min-width / gap (Comfortable / Cozy / Compact).

## 5. Elevation

Three levels only:
1. **Canvas** `--bg` — the page.
2. **Surface** `--surface` with `--border` — cards, side panels.
3. **Floating** `--surface-2` + one soft shadow + `--border-strong` — dialogs,
   popovers, command palette, toasts.

Hover = move one step toward `--surface-2`, never a shadow pop.

## 6. Iconography

`lucide-react`, 1.5px stroke, sized to text (16/18/20). Icons support labels;
they don't replace them in nav. Source-type glyphs: YouTube/article/pdf/podcast.

## 7. Motion

`motion` (Framer), used sparingly. Durations 120–200ms, ease-out.

| Interaction | Motion |
|---|---|
| Card / row hover | 120ms bg + 1px border, no transform jump |
| Route change | 150ms fade + 4px rise of main column |
| Reader open | shared-ish: card → full view, 180ms |
| Toast in/out | slide+fade 160ms |
| Task progress | width transition on the bar, 300ms linear |
| Skeleton | subtle shimmer (respect `prefers-reduced-motion`) |

Always honor `prefers-reduced-motion: reduce` → disable transforms/shimmer.

## 8. Core components (shadcn-based, owned)

shadcn primitives to pull in: `button, input, badge, card, dialog, dropdown-menu,
command (cmdk), popover, tooltip, tabs, scroll-area, skeleton, sonner (toast),
select, switch, separator, avatar, hover-card`.

Custom components composed on top:

- **`AppShell`** — sidebar + topbar + content slot; owns Cmd-K + shortcuts.
- **`Sidebar`** — `WORKSPACE` / `SOURCES` eyebrow groups, nav items with counts.
- **`Omnibox`** — paste-URL-or-ask input (classifier: URL → ingest, text → chat).
- **`ItemCard`** — thumbnail (16:9, object-cover to kill YouTube letterboxing),
  duration badge, title, mono meta line, status dot, tag pills, summary snippet.
- **`StatTile`** — eyebrow label + big number (Today / Insights).
- **`TaskRow`** — status dot + message + progress bar (SSE-driven).
- **`CitationCard`** — source title + snippet + open-in-reader.
- **`Markdown`** — react-markdown wrapper with prose styles + `[[wikilink]]` →
  clickable node (Tier 2).
- **`EmptyState` / `ErrorState` / `<Skeleton variants>`** — the required states.
- **`TagInput`** — add/remove tags with optimistic update.

## 9. State patterns (visual)

Every list/detail surface defines all four:

- **Loading** — skeletons that match final layout (card grid → card skeletons;
  reader → title + paragraph blocks). Never a centered spinner on a full page.
- **Empty** — `EmptyState`: icon + one line + a primary action (e.g. "Add your
  first source"). No dead ends.
- **Error** — `ErrorState`: what failed + a retry button; for ingest failures,
  surface the actual message (e.g. the yt-dlp/Groq error) with a Retry.
- **Partial / streaming** — chat shows tokens as they arrive; ingest shows the
  live `TaskRow`; optimistic edits show immediately, reconcile on success.

## 10. Accessibility & input

- Radix gives focus management/roles for free — don't fight it.
- Visible focus ring (`--border-strong`, 2px) on all interactive elements.
- Full keyboard reachability; Cmd-K and shortcuts documented in
  `FRONTEND_V3_PATTERNS.md`.
- Contrast: body text ≥ 4.5:1 on its surface; check the muted tokens in-browser.
- Hit targets ≥ 32px; tooltips for icon-only controls.
