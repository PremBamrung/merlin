# Merlin UI — Native-First Rebuild Plan

> Course-correction after the first redesign looked bad on the 4K. Supersedes
> the styling approach in `UI_REDESIGN_PLAN.md` (the *features* there stay; the
> *implementation technique* is what was wrong). Reference: the `apple_health`
> Streamlit dashboard in `~/misc/apple_health`, which looks clean and feels good.

---

## 1. Root-cause analysis — why the current Merlin UI looks broken

While debugging the screenshots I confirmed the failure is **not** taste, it's a
broken technique:

1. **Injected CSS never applied.** `ui/theme.py` ships a ~200-line stylesheet via
   `st.html("<style>…</style>")`. Streamlit runs `st.html` through **DOMPurify**,
   which strips/garbles a stylesheet that uses `@import`, `:has()`,
   `::-webkit-scrollbar`, `@media`, `aspect-ratio`, attribute selectors, etc.
   Net result: **none of my `.m-*` classes exist in the DOM.** Every custom
   component fell back to raw, unstyled `<div>`s:
   - the "stat strip" rendered as a vertical text list (Total / 788 / Completed…),
   - eyebrows weren't uppercase/mono,
   - card titles centered (tertiary button default), thumbnails letterboxed,
   - nothing was width-capped or centered → content hugged the left on the 4K.
2. **The accent is Streamlit's default red, not my indigo.** The `[theme]` in
   `config.toml` parses (verified with `streamlit config show`) but the running
   app shows `#FF4B4B` on buttons/segmented controls/pagination — i.e. only
   `base="dark"` took effect. Whatever the cause, **I never visually verified it
   in a real browser** — I trusted `AppTest`, which renders logic, not CSS. That
   is the process failure behind all of this.
3. **I rebuilt a design system Streamlit already provides.** Custom HTML cards,
   pills, eyebrows, queue rows — all reimplementing things `st.metric`,
   `st.container(border=True)`, `st.subheader`, `st.badge`, `st.progress` do
   natively and correctly.

**Conclusion:** stop fighting Streamlit. The fix is to delete the injected-CSS
design system and build with native components, exactly like `apple_health`.

---

## 2. Why `apple_health` looks good (the patterns to copy)

It has **zero custom CSS** and **no `config.toml`** — `utils/styles.py` is only a
Plotly template name + a color dict *for charts*. The polish comes entirely from:

| Technique | Where | What it buys |
|---|---|---|
| `st.title()` / `st.subheader()` | page + section heads | Big, bold, consistent hierarchy (default Source-Sans heading font looks great) |
| `st.metric(label, value, help=…)` | the 4-up stat row | Clean stat cards with big numerals + hover help — **native, no HTML** |
| `st.divider()` | between sections | Calm visual rhythm |
| `st.columns()` | metric rows, side-by-side charts | Responsive layout that stacks on mobile |
| `st.tabs()` | "Active Energy / Exercise / Stand" | Grouping without clutter |
| Rich **Plotly** (`plotly_dark`) | every section | The visual *weight* — heatmaps, area charts, violins, polar, maps |
| Real **sidebar** | data source, status, **date range** | Controls live in the sidebar; main area is content-only |
| `st.success/warning/info` | "Data ready ✓" | Native status, no custom badges |
| `st.navigation([st.Page("pages/…")])` | routing | Standard MPA |
| Default Streamlit **dark** theme | — | Already a good-looking near-black dark; accent used sparingly |

The lesson: **native components + clear hierarchy + a few rich visualizations.**
Merlin is content-centric (not metrics-centric), but the same principles apply —
and Merlin already has a rich visual asset it underuses: **YouTube thumbnails.**

---

## 3. New philosophy

1. **Native-first.** Build every surface from Streamlit widgets. No bespoke HTML
   "cards." Reach for HTML only for a *single, tiny* purpose if unavoidable.
2. **No injected stylesheet.** Delete `ui/theme.py`'s `_STATIC_CSS`. If any CSS
   survives, it is ≤15 lines, applied via `st.markdown(unsafe_allow_html=True)`
   (the method that actually works), and **visually verified**.
3. **Theme via `config.toml` only**, kept minimal so it reliably applies.
4. **Verify in a real browser.** Install Playwright + Chromium; screenshot every
   page at 1280px and at ~1920px before declaring anything done. No more trusting
   `AppTest` for appearance.
5. **Keep all the features** from the first pass (omnibox, reader, library
   filters/sort/density, chat upgrades, theme toggle) — only the rendering
   technique changes.

---

## 4. Theme decision

Minimal `.streamlit/config.toml` — only keys that reliably apply, no
`fontFaces`/`baseRadius`/`buttonRadius`/`[theme.sidebar]` experiments:

```toml
[theme]
base = "dark"
primaryColor = "#7c83ff"          # indigo accent (verify it renders, not red)
backgroundColor = "#0d0d10"        # near-black, OLED-friendly
secondaryBackgroundColor = "#17171c"
textColor = "#ededf2"
font = "sans serif"                # default Source Sans — proven, looks good
```

- **First task is to prove this applies** (screenshot: a primary button must be
  indigo, not red). If `primaryColor` still won't take, debug it for real
  (browser localStorage theme override, version quirk) before building on top.
- **Theme toggle:** Streamlit can't hot-swap `config.toml` at runtime, and the
  CSS-variable trick is what just failed. So either (a) **drop the in-app toggle**
  and ship a great default dark (Streamlit's ☰ menu still lets the user pick
  Light), or (b) keep a toggle that only swaps the Plotly template + accent via
  the *supported* `st.html` style-only path, verified. **Recommendation: (a)** —
  dark-only, OLED-tuned. Revisit a toggle later if it still matters. (Decision to
  confirm with you.)

---

## 5. Per-view rebuild (custom-HTML → native)

### Global
- Delete `ui/theme.py` stylesheet + `inject_theme()`. Keep `tag_color()` (pure,
  used for chart/pill colors) in a slim `ui/styles.py` (color constants only,
  apple_health-style).
- Page heads: `st.title("Library")`, sections: `st.subheader(...)`,
  separators: `st.divider()`. Drop `page_header`/eyebrow HTML.
- Move the **theme/info** out of a custom header row; if kept, use the sidebar.

### Today
- **Greeting:** `st.title("Good evening")` + `st.caption(date · N this week)`.
- **Omnibox:** keep the `st.form` + `st.text_input` + `st.form_submit_button`
  (already native) — just drop the HTML hint; use `st.caption`.
- **Stats:** `st.columns(3)` + `st.metric("Total", n)`, `st.metric("Completed", …)`,
  `st.metric("Needs attention", …)`. (Replaces the broken stat strip.)
- **Recently added:** `st.columns(N)`; each card = `st.container(border=True)`
  with `st.image(thumbnail, use_container_width=True)`, `st.markdown("**title**")`,
  `st.caption("channel · date")`, and a native `st.button("Open")` (or make the
  title a small `st.page_link`/button). Native border = clean card.
- **Active ingest:** `st.progress(pct, text=…)` rows inside the existing fragment.

### Library
- **Toolbar:** keep native `st.text_input` (search), `st.selectbox` (sort),
  `st.segmented_control` (view, density), `st.pills` (tags) — these are already
  native and fine.
- **Cards:** same native card pattern as Today (`st.container(border=True)` +
  `st.image` + `st.markdown` + `st.caption` + `st.button`). Tags via
  `st.badge`/`st.caption` with the `tag_color`. **Thumbnail letterboxing fix:**
  use the 16:9 `mqdefault`/`hqdefault` and `st.image(use_container_width=True)`;
  if black bars remain, switch the thumbnail URL to the 16:9 variant.
- **Grid:** chunk into `st.columns(density)` rows (already done).
- Reader open: native `st.button` → set `?item=` / session (already working).

### Reader
- Already mostly native (`st.markdown` summary, `st.link_button`,
  `st.download_button`, `st.segmented_control`, `st.popover`, `st.text_input`).
  Just remove the HTML title/meta/pill block → `st.title(item.title)` +
  `st.caption(meta)` + `st.badge(source_type)`. Keep timestamp deep-links as a
  native `st.markdown` link list.

### Ingest
- Already native (`st.text_input`, `st.segmented_control`, `st.expander`,
  `st.multiselect`, `st.button`). Drop the eyebrow HTML; use `st.subheader`.
  Task panel → native `st.progress` rows.

### Chat
- Already native (`st.chat_message`, `st.write_stream`, `st.chat_input`,
  `st.popover`, `st.button`). Citations: replace the HTML `m-src` cards with
  `st.container(border=True)` + `st.markdown`/`st.caption` + `st.link_button`
  ("YouTube ↗"). Follow-ups/examples: native `st.button` in columns (fine).

---

## 6. Add richness (the apple_health "wow"): a few Plotly visuals

Merlin is text-heavy; a couple of `plotly_dark` charts make it feel substantial
and intentional. Add **Plotly** (already transitively available, else add to
deps) and an `ui/charts.py` (apple_health-style `_base()` helper):

- **Today / new "Insights" page:**
  - **Ingest activity calendar heatmap** — items added per day (GitHub-style),
    over the library's lifetime. Immediately makes Today feel rich.
  - **Top channels / tags** — horizontal bar of most-frequent channels or tags.
  - **Items by month** — bar of ingests per month.
  - **Summary length / status mix** — small donut.
- Charts use the `tag_color`/accent palette and `template="plotly_dark"`,
  `use_container_width=True` so they scale on the 4K.

This is optional-but-recommended; it's the cheapest way to close the "feels
designed" gap, and the data (788 items with dates/channels) is already there.

---

## 7. Verification (the part I skipped last time)

Make appearance-verification a hard gate:

1. `uv add --dev playwright pytest-playwright` (or a lightweight script) +
   `playwright install chromium`.
2. A `scripts/shoot.py` that boots the app (or points at a running one),
   navigates to each page (`/`, `/ingest`, `/library`, `/library?item=…`,
   `/chat`), and saves PNGs at **1280×800** and **1920×1080**.
3. **I inspect every screenshot** and check: accent is indigo (not red), stat row
   is horizontal metrics, cards have thumbnails + aligned titles, content is
   centered/!left-hugging, no raw unstyled `<div>` text. Only then is a phase done.
4. Keep the `AppTest` smoke tests for *logic* (no exceptions, reader open/close),
   but never again treat them as proof of looks.

---

## 8. Build order

| Phase | Work | Gate |
|---|---|---|
| 0 | Set up Playwright screenshotting; prove the minimal `config.toml` accent renders **indigo** in a real browser | Screenshot shows indigo primary |
| 1 | Delete `ui/theme.py` stylesheet + `inject_theme`; add slim `ui/styles.py` (colors only); strip `st.html` from `page_header` (or replace with `st.title`+`st.caption`) | App renders with native heads, no unstyled HTML |
| 2 | Today: native metrics + native cards + native progress | Screenshot review |
| 3 | Library + Reader: native cards, fix thumbnails, native title/meta | Screenshot review |
| 4 | Ingest + Chat: native task rows + native citation cards | Screenshot review |
| 5 | `ui/charts.py` + 2–4 Plotly visuals on Today/Insights | Screenshot review |
| 6 | Full screenshot sweep (both widths) + `AppTest` logic smoke + ruff | All green + I sign off on every PNG |

Each phase ends with a real screenshot I actually look at.

---

## 9. Keep / cut

**Keep (functional wins from pass 1):** omnibox + routing, in-session reader
open (state-preserving), library search/sort/view/density/tag filters, reader
copy/export/timestamps/re-summarise/tags, chat regenerate/follow-ups/inline
sources, the `sort` repo param, `retry(summary_length=…)`. All the service-layer
work stays.

**Cut:** the entire injected-CSS design system (`_STATIC_CSS`, `inject_theme`,
`m-*` classes, `_root_block`), the eyebrow/pill/stat-strip/queue HTML, the
`reader_href` query-link cards. Replace with native widgets.

**Open questions for you:**
- Theme toggle: drop it for a polished dark-only (my rec), or keep a verified one?
- Add the Plotly visuals / an **Insights** page (rec: yes), or keep it minimal?
