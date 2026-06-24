# Agentic Chat — Improvement Analysis

Analysis of (A) a concrete copy-button bug and (B) the in-chat LLM's own feedback
on what the agentic system is missing, triaged against what the codebase actually
supports. **Analysis only — see `CHAT_AGENT_RETRIEVAL_PLAN.md` for the fix plan.**

---

## Part A — The copy-button asymmetry

**Symptom:** the user can copy *every* user message but only the *last* assistant
message.

**Root cause — one line.** `web/src/components/chat/Message.tsx:154`

```ts
const showActions = isLast && !isThisStreaming && !!textContent;
```

The assistant's `Copy` button lives inside the `showActions` block
(`Message.tsx:216-234`) alongside `Regenerate` and the follow-up chips. The whole
row is gated on `isLast`, so **Copy only renders on the most recent assistant turn.**

The user bubble copies differently (`Message.tsx:296-321`): its `CopyButton` is a
hover affordance (`opacity-0 … group-hover:opacity-100`) tied to `onEdit` being
present, **not** to `isLast`. That asymmetry is the whole bug.

This is not a copy-logic bug — `textContent` is computed correctly for every
assistant message (`Message.tsx:118-123`). It's a **placement** decision: Copy got
bundled with two actions that genuinely only make sense on the last turn:

- **Regenerate** — you can only re-run the latest answer.
- **Follow-ups** — they continue from the latest turn.
- **Copy** — makes sense on *every* turn, but inherited `isLast` by sharing the row.

**Fix direction:** split Copy out of `showActions` and give assistant turns the
same hover-reveal Copy the user turns have (e.g. in the `✦ Merlin` header row at
`Message.tsx:164-170`). Keep Regenerate + follow-ups gated on `isLast`. Small,
isolated change.

---

## Part B — The LLM's system feedback, triaged against the code

The LLM's list is directionally good but doesn't know what's already wired up.
Mapping each complaint to the real code changes the priorities sharply.

> **Headline: half of its top complaints are not missing data — the data already
> exists and simply isn't passed into the tool output.**

### 🟢 Already-present data, just not exposed to the agent (cheap, high-impact)

| LLM complaint | Reality in code | Gap |
|---|---|---|
| #1 "No publication dates" | `knowledge_items.published_at` exists (`models.py:43`); YouTube has `published_at`, `views`, `duration`, `channel` (`models.py:99-101`). `serialize_item` already returns all four (`library.py:27,41-43`). | `_format_chunks`/`_format_item`/`_format_browse` (`agent.py:246-287`) **never emit dates**. The agent literally cannot see fields sitting in the dict it's handed. |
| #6 "I don't know what I don't have" | `browse_library` already returns `"{total} item(s) match; showing {len}"` (`agent.py:279`). | `search_library` (`_format_chunks`) returns **no count, no coverage signal**. Adding a total / "N more not shown" line directly answers the coverage complaint. |
| #4 "Transcripts truncated, no way to continue" | `get_item` hard-caps at `_TRANSCRIPT_EXCERPT_CHARS = 3000` and appends `…[transcript truncated]` (`agent.py:271-273`). | Confirmed real. No paging/offset arg, no "search within transcript" tool. A `get_item(item_id, offset=…)` closes it. |

These three are the **highest ROI** — framed as architectural gaps, they're really
"the tool serializers drop fields the DB already has."

### 🟡 Real infrastructure work (genuinely missing)

- **Semantic/vector search (its #1 system ask).** Correct and well-aimed.
  `retriever.py` is FTS5 keyword-only; the `embeddings` table exists but is unused
  ("Phase 3"). The one item that's both *real* and *foundational* — already
  scaffolded in the design. Everything else ("I try 6 phrasings") is downstream.
- **Structured tags (version / class / mode).** Half data-quality, half tooling.
  `list_tags` and per-item `tags` exist, but tags are free-form and sparse. The
  agent can't filter on `version:3.6` because nothing *writes* that tag. An
  ingestion/auto-tagging problem more than a chat problem.
- **Cross-session memory / user profile.** Genuinely absent. `chat_threads`
  persists conversations but there's no user-level profile store.

### 🔴 Over-reach / domain-specific (defer or decline)

- **Knowledge graph of entities** (#3) — very high complexity, largely redundant
  once semantic search + dates exist; the concrete wins it cites are mostly solved
  by better retrieval + the agent already calling `search_library` repeatedly.
- **Stuff stat comparator / simulation** (#7, #2) — Dofus-specific, out of scope
  for a general KM tool. The LLM itself flags this as "dreaming."
- **Source confidence scoring** — cheap (item-count per channel, recency) but low
  marginal value until dates + semantic search land; a ranking tweak, not a
  capability.

### Recommended order

1. **Expose `published_at` + counts in tool output** (+ optional date/sort filter)
   — kills #1 and #6; the agent stops guessing recency from titles.
2. **Transcript paging on `get_item`** — kills #4.
3. **Vector search (hybrid + RRF)** — the foundational investment; turns
   "6 phrasings" into one.
4. Auto-tagging at ingest (version/class/mode) → unlocks structured filters.
5. Cross-session profile / confidence scoring — later, lower leverage.

The through-line: the LLM describes symptoms as deep architectural holes, but
**#1, #4, #6 are serializer-level fixes against data already stored.** Do those
first.
