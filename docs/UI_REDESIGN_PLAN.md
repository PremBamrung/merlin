# Merlin — UI/UX Redesign Plan

> Plan only. No code changes yet. Companion to `STREAMLIT_MIGRATION_PLAN.md`
> (which covered the *architecture* move back to Streamlit). This covers the
> *look, feel, and interaction* of the `ui/` layer that sits on top of it.

---

## 1. Why the current UI feels off (diagnosis)

The current app is a **faithful but flat reproduction of the abandoned v2 React
frontend's layouts** — without the design system that made v2 feel intentional.

What v2 had (recovered from `frontend_v2/styles.css` + `screen-*.jsx` in git
history `7f9cfed~1`):

- A real **design system**: dual themes (*Obsidian* warm-charcoal dark +
  *Papyrus* warm-cream light), **Inter + JetBrains Mono**, a tunable accent
  hue, a radius/shadow/duration scale, slim scrollbars.
- **Density and hierarchy**: mono microcopy for metadata/numbers, uppercase
  tracked labels, colored tag dots, confidence bars, an omnibox, queue rows
  with stage dots.

What the current Streamlit app does instead:

- `base="light"` and nothing else — **default Streamlit chrome**.
- Emoji-in-title headers (`🏠 Today`, `📚 Library`).
- Plain `st.container(border=True)` cards, `st.metric`, default fonts.
- v2's **2-column split layouts** (`[3,2]` on Today and Ingest) ported
  literally — which on Streamlit produces a thin cramped right rail and reads
  like a wireframe.
- A **cramped `st.dialog`** for item detail (the most-used surface).

So the structure imitates v2 but the surface is generic, and some v2 layout
choices don't translate to Streamlit's component model. **The fix is not "less
Streamlit"** — it's (a) a proper design system applied via Streamlit 1.58
theming + a thin CSS layer, (b) layouts that suit Streamlit rather than mimic
React, and (c) a few targeted interaction upgrades.

### Locked decisions (from review)

| Decision | Choice |
|---|---|
| Aesthetic | **Clean modern neutral** — Linear/Vercel-ish. True-black OLED dark + crisp light. Inter (UI/headings), mono for numbers/meta. Indigo accent. |
| Default theme | **Dark by default**, in-app **☀️/🌙 toggle** (OLED is the primary screen). |
| New features | **All four**: Today omnibox · Reader view · Library polish · Chat upgrades. |

---

## 2. Design system (tokens)

A single source of truth for tokens lives in **`ui/theme.py`** (new). Two token
sets — `DARK` (default) and `LIGHT` — plus a runtime toggle.

```
                         DARK (default, OLED)        LIGHT
  bg (app)               #0a0a0b                     #ffffff
  surface (cards)        #141416                     #ffffff
  surface-2 (insets)     #1b1b1f                     #f4f4f5
  border                 rgba(255,255,255,0.09)      rgba(0,0,0,0.10)
  text                   #ededef                     #18181b
  text-muted             #a1a1aa                     #52525b
  text-faint             #6b6b73                     #a1a1aa
  accent (indigo)        #818cf8  (hover #a5b4fc)     #6366f1 (hover #4f46e5)
  accent-soft            rgba(129,140,248,0.14)       rgba(99,102,241,0.10)
  good / warn / danger   #4ade80 / #fbbf24 / #f87171  #16a34a / #d97706 / #dc2626
  radius                 sm 6px · md 10px · lg 16px
  font-ui                Inter, -apple-system, system-ui, sans-serif
  font-mono              "JetBrains Mono", "SF Mono", Menlo, monospace
```

Dark uses **near-black `#0a0a0b`, not pure `#000`**, and cards a hair lighter —
true blacks plus one elevation step read as "deep" on OLED without smearing.
No pure-white surfaces in dark mode.

**Tag dot palette** (deterministic per tag, used as the colored chip dot):
hash the tag name → pick from an 8-swatch indigo/teal/amber/rose/violet/green
ramp. Same tag → same color everywhere (library chips, reader, filters).

---

## 3. Theming implementation in Streamlit 1.58

Two layers, smallest-footprint first:

### 3a. `.streamlit/config.toml` — the base (dark) theme

Replace the current 2-line file with the full 1.58 theme surface so most of the
look is **native** (no CSS needed for it):

```toml
[theme]
base = "dark"
primaryColor = "#818cf8"
backgroundColor = "#0a0a0b"
secondaryBackgroundColor = "#141416"
textColor = "#ededef"
linkColor = "#a5b4fc"
borderColor = "rgba(255,255,255,0.09)"
codeBackgroundColor = "#1b1b1f"
showWidgetBorder = true
baseRadius = "10px"
buttonRadius = "8px"
font = "Inter"
headingFont = "Inter"
codeFont = "JetBrains Mono"
# baseFontSize ~15 for desktop comfort; see responsive note (§4)
baseFontSize = 15

# Load the web fonts so `font`/`codeFont` resolve offline-ish (Docker too).
[[theme.fontFaces]]
family = "Inter"
url = "https://fonts.gstatic.com/.../Inter.woff2"   # (or bundle in ui/assets/)
weight = "400 800"
[[theme.fontFaces]]
family = "JetBrains Mono"
url = "https://fonts.gstatic.com/.../JetBrainsMono.woff2"
weight = "400 600"

[theme.sidebar]
backgroundColor = "#0d0d0f"
borderColor = "rgba(255,255,255,0.07)"
```

> Note: config.toml defines **one** active theme. The base/default = dark. The
> light variant for the toggle is applied at runtime (3b). For Docker
> reliability, **bundle the woff2 files under `ui/assets/`** and point
> `fontFaces.url` at them via a static path rather than Google's CDN.

### 3b. `ui/theme.py` — runtime toggle + thin CSS polish

Streamlit can't hot-swap the config theme at runtime, so the toggle works by
**injecting CSS custom properties** keyed on `st.session_state.theme`
(`"dark"` | `"light"`, default `"dark"`). One `st.html("<style>…")` block per
run, emitted from `app.py` before navigation:

```python
# ui/theme.py
DARK  = {...tokens...}
LIGHT = {...tokens...}

def inject_theme() -> None:
    tokens = LIGHT if st.session_state.get("theme") == "light" else DARK
    st.html(f"""<style>
      :root {{ --bg:{tokens['bg']}; --surface:{tokens['surface']}; ... }}
      /* App shell */
      .stApp {{ background: var(--bg); }}
      .block-container {{ max-width: var(--content-max); padding-top: 2.2rem; }}
      /* Cards, chips, mono microcopy, slim scrollbars, etc. */
      .merlin-card {{ background: var(--surface); border:1px solid var(--border);
                      border-radius: var(--r-md); transition: ... }}
      .merlin-card:hover {{ border-color: var(--accent); }}
      .mono {{ font-family: var(--font-mono); }}
      ...
    </style>""")

def theme_toggle() -> None:
    # ☀️/🌙 button in the top area; flips session_state.theme + st.rerun()
```

The CSS layer is **deliberately small**: it only does what config.toml can't —
the runtime variable swap, card/chip styling, mono microcopy class, slim
scrollbars, and the content-width cap (§4). Everything color/font/radius that
config.toml already covers is **not** duplicated in CSS.

> Why CSS at all, given "it isn't Streamlit's fault"? Because the polish that
> made v2 feel good (density, mono numerals, colored tag dots, hover affordance)
> lives in ~120 lines of CSS, not in a framework choice. This is the
> Streamlit-native way to get it.

**Toggle persistence:** session-scoped via `session_state` (resets on hard
reload — acceptable). Optionally persist to `st.query_params` (`?theme=light`)
so a reload/bookmark keeps it; note as a small nice-to-have.

---

## 4. Multi-device / responsive strategy

Target devices: **32" 4K OLED (primary)**, 27" 2K IPS, 16" MacBook Pro, iPhone 17.

The two real problems with `layout="wide"` across this range:

1. **4K → absurd line lengths.** Wide mode stretches text full-bleed; reading a
   summary across 3840px is miserable.
2. **iPhone → cramped fixed grids.** `st.columns(3)` does auto-stack vertically
   on narrow viewports (Streamlit handles this), but card internals tuned for
   desktop look off.

Plan:

- **Content-width cap.** `.block-container { max-width: 1180px; margin-inline:auto }`
  for reading-centric views (Today, Reader, Chat, Ingest). The Library grid gets
  a **wider cap (~1600px)** so 4K shows more cards. This single rule fixes the 4K
  problem without media queries.
- **Density control instead of viewport detection.** Streamlit can't reliably
  read viewport width server-side, and JS round-trips are fragile. So the Library
  toolbar gets a **segmented density control — Comfortable (2) · Cozy (3) ·
  Compact (4)** columns. The user picks per device once; it persists in
  `session_state`. This is more robust than auto-detection *and* doubles as a
  genuinely useful feature (more cards on the 4K, fewer on the MBP).
- **Mobile (iPhone).** Rely on Streamlit's native column collapse; verify each
  card/omnibox/chat input renders at 1-col. Add a CSS `@media (max-width:640px)`
  block to: shrink `baseFontSize` feel via padding, hide non-essential mono
  microcopy, make the theme toggle + omnibox full-width. Sidebar nav already
  collapses to the hamburger on mobile (Streamlit default).
- **Touch targets.** Buttons/chips min-height 36px so they're tappable on
  iPhone and precise with a mouse on the 4K.

No per-device hacks beyond the density control + one mobile media query — keeps
it maintainable.

---

## 5. Per-view redesign

Common chrome (applies to all views):

- **Drop emoji-in-`st.title`.** Use a consistent page header component:
  `ui/components/page_header.py` → `page_header(title, subtitle=None, actions=None)`
  rendering a left-aligned title (Inter 700, tight tracking) + muted mono
  subtitle, with an optional right-aligned action slot (where the **theme
  toggle** and page-level actions live).
- Icons stay in the **sidebar nav** (already `:material/…`), not in titles.

### 5a. Today — dashboard + **omnibox** (feature)

Current: 3 metrics, a `[3,2]` split (recent list left, task rail right).

Redesign:

- **Greeting + date line** in mono microcopy (`MONDAY, JUNE 11 · 11 added this
  week`) — derived from real counts via `library.list_items`.
- **Omnibox** (the v2 centerpiece, `ui/components/omnibox.py`): one full-width
  `st.text_input` (or `st.chat_input`-style) with a sparkle icon and a smart
  hint that updates on input:
  - looks like a URL (`re.search(r'https?://|youtu|\.\w{2,}/' …)`) → **"Press
    Enter to ingest"**; on submit calls `ingest.submit_youtube(url,
    session_langs, session_length)`, toasts the task id, and the task panel
    below shows progress.
  - otherwise → **"Press Enter to ask your library"**; on submit stashes the
    text in `session_state.pending_question` and `st.switch_page` → Chat, which
    auto-submits it.
  - Routing logic is a tiny pure helper `omnibox_route(text) -> ("ingest"|"ask",
    payload)` (unit-testable, no Streamlit).
- **Stat strip** restyled: 3 compact metrics as a single bordered row with mono
  numerals (Total · Completed · Needs attention), accent on the number.
- **Recently added**: reuse the new card component (§6) in a 2-col grid, not the
  bespoke inline `[1,3]` layout. Cap at 6.
- **Ingesting** queue: replace the cramped right rail with a **full-width**
  list of slim queue rows (stage dot + title + thin progress bar + mono stage
  label), only shown when something is active. This is `task_panel` restyled
  (still the `@st.fragment(run_every=2)` self-refresh).

Net: Today becomes a single centered column (capped width) — omnibox → active
queue → recent grid. No more thin side rail.

### 5b. Library — polish + **Reader view** (features)

Current: filters row, 3-col grid of plain cards, `st.dialog` detail.

Redesign — **toolbar**:

- Search input with a **`/`-to-focus** hint chip (CSS `kbd` style). True global
  `/` focus needs a key listener; ship the visual `kbd` + autofocus on the
  search box, and note JS-key-capture as optional.
- **Source-type filter chips with counts** (`Everything 788 · YouTube 788 · …`)
  — currently only YouTube exists, so this is built to scale but shows one chip
  now; keep it as a styled segmented control.
- **Colored tag chips as quick filters** (replaces the bare `st.multiselect`):
  top ~8 tags from `library.list_tags()` rendered as toggleable chips with their
  deterministic dot color; "more" opens a popover with the full multiselect.
- **Sort** select: Newest · Oldest · Longest · Title A–Z (maps to repo
  ordering; needs a `sort` param threaded through `library.list_items` →
  `KnowledgeItemRepository.list_all` — small service/repo addition).
- **Grid/List toggle** + the **density control** (§4).

**Cards** (`ui/components/item_card.py` rewrite): clickable card (not a separate
"Open" button), 16:9 thumbnail with duration pill + play glyph overlay, title
(2-line clamp), mono meta (channel · date), colored tag dots, status dot. Click
sets `?item=<id>` query param.

**Reader view** (replaces the dialog — `ui/views/reader.py` or a mode inside
library): when `st.query_params.get("item")` is set, render a **full-width
centered reading view** instead of the grid:

- `← Back` (clears the query param), title, mono meta line (channel · duration ·
  language · ingested date), status.
- **Summary** rendered as proper markdown at reading width (the cap from §4),
  comfortable line-height — the thing this app is *for*, finally given room.
- **Topics & timestamps** as **deep links into YouTube**: each
  `topic → HH:MM:SS` becomes a link `https://youtube.com/watch?v={source_id}&t={secs}s`
  (convert `HH:MM:SS`→seconds). Uses existing `item["topics"]` /
  `youtube_metadata.timestamps`.
- **Actions row**: Open on YouTube · Copy summary (markdown) · Export `.md`
  (`st.download_button`) · Re-summarise · Edit tags (inline, colored chips) ·
  Delete (with confirm).
- Summary-length switch (short/medium/long) that triggers a re-summarise at the
  chosen length (reuses `ingest.retry` + a length arg — small extension).

Why a routed reader vs. dialog: dialogs are width-capped and modal — bad for the
primary reading surface on a 4K. A query-param-driven full view is shareable,
back-button friendly, and uses the whole screen. (Keeps the `st.dialog` pattern
only for quick destructive confirms.)

### 5c. Ingest

Current: `[3,2]` form-left / task-rail-right; URL + languages multiselect +
length select + Summarize.

Redesign:

- Single centered column. The omnibox on Today covers the fast path; Ingest is
  the **"power" entry** with full control.
- Group the controls in a bordered "New source" card: URL field; **languages**
  kept but defaulted and tucked into an "Advanced" `st.expander` (most ingests
  are `["en"]`); **length** as a 3-button segmented control (short/medium/long)
  instead of a select.
- After submit, the **task panel moves below** the form full-width (same
  restyled queue rows as Today), so progress isn't squeezed into a rail.
- Light input validation feedback inline (the service already raises
  `ValueError`; surface it on the field).

### 5d. Chat — **upgrades** (feature)

Current: popover tag filter, clear button, history replay, `st.write_stream`,
citations in an expander.

Redesign:

- **Auto-submit from omnibox**: on entry, if `session_state.pending_question`
  is set, consume it as the first prompt.
- **Header**: title + context-filter popover (tags) + Clear, in the shared
  `page_header` actions slot.
- **Streaming answer** unchanged mechanism (`st.write_stream`), but wrapped so
  we can append a small **action bar under each assistant message**: Copy
  answer · Regenerate (re-runs the last user turn) · 👍/👎 (optional, no-op or
  logged).
  - **Stop**: honest constraint — Streamlit's exec model can't cleanly
    interrupt a running generator mid-`write_stream`. Scope = **no true stop
    button** in v1; Regenerate covers the common need. (Documented, not faked.)
- **Inline source cards** (replace the bare expander list,
  `ui/components/citation_list.py` rewrite): per citation, a compact card with
  source-type pill, title, author (mono), the **excerpt** (already on
  `RetrievedChunk`), and two links: **Open in reader** (`?item=<id>`) and **Open
  on YouTube**. Per-chunk timestamps aren't available from FTS, so we link to
  the item (whose reader has the timestamped topics) rather than fabricate a
  time.
- **Suggested follow-ups**: 3 chips under the answer. v1 = cheap heuristic
  (derive from citation titles / "Tell me more about X"); note an optional LLM
  one-liner upgrade later.
- Empty state: a few example prompts as clickable chips.

---

## 6. New / changed files

```
.streamlit/config.toml         REWRITE  full dark theme + fonts (§3a)
ui/assets/                      NEW      bundled Inter + JetBrains Mono woff2
ui/theme.py                     NEW      tokens, inject_theme(), theme_toggle(), tag_color()
ui/components/page_header.py    NEW      consistent header + actions slot
ui/components/omnibox.py        NEW      Today omnibox + omnibox_route() pure helper
ui/components/item_card.py      REWRITE  clickable card, thumb overlay, tag dots, clamp
ui/components/citation_list.py  REWRITE  inline source cards w/ links + excerpt
ui/components/task_panel.py     RESTYLE  slim queue rows (stage dot + bar), full-width
ui/views/today.py               REWRITE  omnibox + stat strip + recent grid + queue
ui/views/library.py             REWRITE  toolbar (chips/sort/density/view), grid, reader route
ui/views/reader.py              NEW      full-width reading view (or a mode in library.py)
ui/views/ingest.py              REWRITE  single column, advanced expander, segmented length
ui/views/chat.py                REWRITE  source cards, action bar, follow-ups, auto-submit
ui/state.py                     EDIT     theme default, density, pending_question helpers
app.py                          EDIT     inject_theme() before nav; add reader page/route
```

Service/repo touch-ups (small, keep the one-way dependency rule intact):

- `merlin/services/library.py` + `repositories/knowledge.py`: add a `sort`
  param to `list_items`/`list_all` (newest/oldest/longest/title).
- `merlin/services/ingest.py`: let `retry()` accept a `summary_length` override
  (for the reader's length switch). Already accepts `languages`.

**Architecture guard unchanged:** all new UI imports `streamlit` + `merlin.services.*`
only; `ui/theme.py` is pure presentation. `tests/test_architecture.py` still
passes (verify it whitelists new `ui/` modules / globs, not a fixed list).

---

## 7. Build order

| Phase | Scope | Outcome |
|---|---|---|
| **0. Foundation** | `config.toml` rewrite + `ui/theme.py` (tokens, inject, toggle) + `page_header`; bundle fonts; wire `inject_theme()` + toggle into `app.py`. | Whole app instantly looks like the new system (dark + toggle), zero feature change. Cheapest, highest visual ROI. |
| **1. Cards & density** | Rewrite `item_card`, add `tag_color`, content-width caps, density control. | Library/Today cards look right across devices. |
| **2. Library + Reader** | Library toolbar (chips/sort/view/density), query-param reader view, summary export/copy/timestamp links. `sort` param in service/repo. | The core surface (browse → read) is excellent. |
| **3. Today omnibox** | Omnibox component + routing, restyled stat strip + queue rows, recent grid. | Dashboard becomes the smart entry point. |
| **4. Ingest** | Single-column form, advanced expander, segmented length, full-width task panel. | Consistent with the rest. |
| **5. Chat** | Inline source cards, action bar (copy/regenerate), follow-up chips, omnibox auto-submit, empty state. | Chat feels first-class. |
| **6. Mobile + polish pass** | `@media` block, touch targets, verify iPhone/4K, slim scrollbars, query-param theme persist. | Works on all four screens. |

Phases 0–2 alone already resolve the "doesn't feel good" problem. 3–5 deliver the
requested features. Each phase is shippable and independently verifiable with
`AppTest` against the real 788-item DB (the migration session already proved that
harness works).

---

## 8. Streamlit constraints to respect (honesty)

- **No runtime swap of the config theme** → the light/dark toggle is done via
  injected CSS variables (§3b), not by rewriting config. Works, but means our
  CSS must cover any element config.toml colored that we also recolor on toggle.
- **No reliable server-side viewport width** → density is a manual control, not
  auto-detection (§4). This is a feature, not a workaround, given the 4 devices.
- **No clean mid-stream "Stop"** for `st.write_stream` → Chat ships Regenerate,
  not Stop, in v1 (§5d).
- **`st.html`/CSS targets Streamlit's DOM classes**, which can change across
  versions. Mitigate by styling our **own class names** (`.merlin-card`,
  `.mono`, etc. that we emit) and using **CSS custom properties** + the official
  `[theme]` keys wherever possible, touching Streamlit's internal classes only
  for the few things config can't reach (block-container width, scrollbars).
  Streamlit is **pinned `>=1.58`**; re-verify the selectors on any bump.
- **`st.switch_page`** is used for omnibox routing — works with `st.navigation`
  pages by their `url_path`/page object; verify under AppTest.

## 9. Explicitly out of scope (for this plan)

- Wiki/Karpathy layer, share links, graph view, inbox/digest/reddit screens
  (deferred in the migration plan; not revisited here).
- Vector search / embeddings (Phase 3, unrelated).
- Accent-hue customization UI (v2 had it; nice-to-have, not now — accent is
  fixed indigo).
- True keyboard-shortcut capture (`/`, ↑/↓) — visual affordance only in v1.
- Auth, multi-user, theming persistence beyond session/query-param.
```
