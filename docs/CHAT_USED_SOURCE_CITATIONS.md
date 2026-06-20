# Plan — Cite only the sources the LLM *used* (inline markers)

> Status: **BUILT.** The LLM emits **inline citation markers**; the backend
> parses them to split **used** vs **viewed** sources. Scope: the agentic
> library-wide chat (`/chat`). The Reader single-item chat is out of scope (no
> Sources list). No DB, no migration, no extra LLM call.
>
> Implementation: prompt marker instruction in `merlin/rag/prompts.py`
> (`AGENT_SYSTEM_PROMPT`); `_citations_emitter` in `api/routers/chat.py` parses
> `[#id]` markers (`_MARKER_RE`, `#` optional, 8+ hex; abbreviated ids resolved
> by unique prefix via `_resolve_marker`) with title-match → all-viewed
> fallbacks and emits `data-citations` (used) + `data-sources-viewed` (viewed).
> The frontend renders **inline superscript citation chips** —
> `linkifyCitationMarkers` (`web/src/hooks/useAgentChat.ts`) rewrites each marker
> into `[n](#cite-<item_id>)` numbered to match the Sources list, and
> `Markdown.tsx` renders that sentinel href as a small pill linking to the item;
> `stripCitationMarkers` is kept for the (clean) copy path. `Message.tsx` renders
> the two tiers (Sources grid + the `AlsoSearched` disclosure). Tests in
> `tests/backend/test_chat.py`.

## 1. Decision

The model tags claims with a marker carrying the item id it used —
`… DJI's moat is its supply chain [#a1b2c3].` The backend, in the existing
`on_complete` hook, parses markers out of the answer, intersects them with the set
of items the tools surfaced, and emits **two** data parts:

- `data-citations` — the **used** items (markers found) → primary **Sources** grid.
- `data-sources-viewed` — the remaining retrieved items → a collapsed
  **"Also searched (N)"** disclosure.

Rationale: the item ids are *already* in the model's context (each search result
is printed as `[<item_id>] <title>`), so no new plumbing is needed to give the
model something to cite; it costs nothing extra (no second LLM call, no structured
output that would break token streaming); and it degrades gracefully — if a model
emits no markers, fall back to a title-match heuristic, and if that finds nothing,
show all viewed (today's behavior). Rejected: a `cite` tool (+1 round-trip),
structured `output_type` (breaks streaming), a relevance-judge pass (cost/latency).

## 2. Current behavior (what changes)

`merlin/rag/agent.py` accumulates **every** touched item into `ChatDeps.cited`:

```python
@agent.tool
def search_library(ctx, query, ...):
    chunks = _retriever.retrieve(...)
    for c in chunks:
        ctx.deps.cite(c)          # cites EVERY retrieved row
@agent.tool
def get_item(ctx, item_id):
    ...; ctx.deps.cite_item(item) # cites whenever read
```

`api/routers/chat.py::_citations_emitter` emits all of `cited` as one
`data-citations` part. There is no answer→source mapping. We keep `cited` as the
"viewed" set and add a "used" set derived from markers.

Each search result already exposes the id the model will cite (`_format_chunks`):
`[<knowledge_item_id>] <title> — <author> (<source_type>)`.

## 3. Build steps

### Step 1 — Prompt (`merlin/rag/prompts.py`, `AGENT_SYSTEM_PROMPT`)
Add a citation-marker instruction. Append to the "Ground every claim" guidance:

> When a sentence draws on a library item, append that item's id marker in square
> brackets with a leading `#`, e.g. `[#a1b2c3]`. The id is the bracketed value
> shown before each search result's title. Mark **only** items you actually used;
> you may put several markers after one sentence. Do not invent ids.

Tune wording during build; keep it short and concrete.

### Step 2 — Track "used" separately (`merlin/rag/agent.py`)
`ChatDeps` keeps `cited` (viewed) as-is. No `used` set is collected *in the tools*
— "used" is derived from the answer text at the end (Step 3), because only the
final text knows what was cited. (Leaving the tools untouched keeps the change tiny.)

### Step 3 — Parse markers + split (`api/routers/chat.py`)
Rewrite `_citations_emitter` to use the `AgentRunResult` it already receives:

```python
import re
_MARKER_RE = re.compile(r"\[#([0-9a-fA-F-]{6,})\]")  # tolerant; ids are uuids/hex

def _citations_emitter(deps):
    async def on_complete(result):
        viewed = deps.cited                      # {item_id: citation}
        text = result.output or ""
        used_ids = {m for m in _MARKER_RE.findall(text) if m in viewed}
        if not used_ids:                         # fallback: title match in answer
            used_ids = {
                iid for iid, c in viewed.items()
                if c["title"] and c["title"].lower() in text.lower()
            }
        used = [viewed[i] for i in viewed if i in used_ids]
        also = [viewed[i] for i in viewed if i not in used_ids]
        if used:
            yield DataChunk(type="data-citations", data={"items": used})
        if also:
            yield DataChunk(type="data-sources-viewed", data={"items": also})
        # If nothing was used AND nothing matched, emit all viewed as citations
        # so a clearly-grounded answer never shows an empty Sources list.
        if not used and not also is False and not used_ids and viewed and not used:
            yield DataChunk(type="data-citations", data={"items": list(viewed.values())})
    return on_complete
```

(Clean up the final fallback branch during implementation — intent: never show an
empty Sources list when the library was clearly used.) Marker regex is tolerant of
both `[#id]` and could be widened to accept `[id]`; keep it strict on the id shape
to avoid matching ordinary brackets.

### Step 4 — Frontend types (`web/src/hooks/useAgentChat.ts`)
The `Citation` type already exists. No new type strictly needed — both parts carry
`{ data: { items: Citation[] } }`. Optionally add a named constant for the two part
types.

### Step 5 — Render two tiers + strip markers (`web/src/components/chat/Message.tsx`)
- Collect `data-citations` items → render as today's **Sources** grid.
- Collect `data-sources-viewed` items → render a collapsed **"Also searched (N)"**
  disclosure (reuse the existing `ReasoningBlock`/`ToolTrace` collapse pattern).
- **Strip the `[#id]` markers from the displayed answer text.** Do it in the text
  render path — either a small `remark`/`rehype` plugin, or a `.replace(_MARKER_RE,
  "")` on each `text` part before passing to `<Markdown>`. Ensure `CopyButton`
  copies the stripped text (it currently copies the concatenated text content).
- Stretch (optional): turn each marker into a superscript chip linking to the
  matching Sources card instead of stripping it.

## 4. Wire shapes

```jsonc
// used
{ "type": "data-citations",      "data": { "items": [ {Citation}, … ] } }
// viewed-but-unused
{ "type": "data-sources-viewed", "data": { "items": [ {Citation}, … ] } }
```
`Citation = { item_id, title, source_type, snippet, score }` (unchanged).

## 5. Test plan (`tests/backend/test_chat.py`)
Use a scripted streaming `FunctionModel` (the existing `_search_then_answer_model`
helper pattern), no network:

1. **Markers split used vs viewed** — model returns 3 search rows, answer text
   includes `[#<id-of-row-1>]`. Assert `data-citations` has row 1 only and
   `data-sources-viewed` has rows 2–3.
2. **No markers → heuristic** — answer names row 2's title verbatim, no markers.
   Assert row 2 ends up in `data-citations`.
3. **No markers, no title match → all viewed cited** — answer is generic; assert
   `data-citations` contains all retrieved rows (no empty Sources list).
4. **Hallucinated id dropped** — answer has `[#deadbeef]` for an id never
   retrieved; assert it's ignored.
5. **Reader path unchanged** — `item_id` request emits no citation parts.

## 6. Acceptance criteria
- An answer that cites 2 of 8 retrieved items shows **2** in Sources and **6** in
  "Also searched."
- Markers never appear in the rendered answer or copied text.
- A model that ignores markers still yields a sensible Sources list (heuristic /
  all-viewed fallback) — no regression to "empty Sources."

## 7. Gotchas
- Markers stream inside `text-delta`s; strip at **render** time, compute the
  used/viewed split only at **`on_complete`** (end of turn) — the Sources list
  resolving last is expected.
- Don't match ordinary prose brackets — require the `#` + id shape.
- Keep `deps.cited` as the viewed superset; "used" is always a subset of it.

## 8. Effort
**Small.** Prompt tweak + ~30 lines in `on_complete` + a frontend two-tier render
and a marker strip. No DB, no migration, no new model call. ~Half a day.
