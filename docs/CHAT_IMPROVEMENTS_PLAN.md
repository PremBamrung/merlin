# Chat tab — improvements plan

Status: **planning only, no code yet.** Scope confirmed = the three named
features below. The rest is a backlog kept here for later.

Surfaces involved:
- `web/src/routes/chat.tsx` — the Chat tab (thread sidebar + conversation pane).
- `web/src/components/chat/Message.tsx` — one rendered turn (shared with Reader).
- `web/src/components/chat/ItemChat.tsx` — Reader per-item chat (ephemeral).
- `web/src/hooks/useAgentChat.ts` — `useChat` wrapper, persisted data-parts.
- `web/src/hooks/useChatThreads.ts` — thread list/detail/save/rename/delete.
- `web/src/lib/format.ts` — `relDate()` helper (already exists).
- Backend (reference only — **not touched** for the chosen scope):
  `api/routers/chat.py`, `merlin/services/chat_history.py`,
  `merlin/db/models.py` (`ChatThread`/`ChatMessage`).

---

## Scope to build now (3 features)

### 1. Conversation timestamps in the sidebar
**Frontend only — data already returned.** `ChatThreadSummary` already carries
`created_at` + `updated_at` (`useChatThreads.ts`), and `relDate()` already
exists. `ThreadRow` just doesn't render them.

- Render `relDate(thread.updated_at)` as a muted line under the thread label in
  `ThreadRow` (`chat.tsx`).
- Group the list by date buckets (Today / Yesterday / Previous 7 days / Older)
  in `ThreadList`, since the API already returns rows ordered by `updated_at`
  descending — bucketing is a pure client-side partition.
- No backend, no schema, no migration.

### 2. Per-message timestamps
**Client-side data-part — decided approach.** The DB `ChatMessage.created_at`
column is unreliable because `save_thread` does a wholesale DELETE+INSERT every
turn (`chat_history.py`), resetting every row's `created_at` to "now". So we do
**not** rely on the backend.

- Mirror the existing `data-work-timing` pattern in `useAgentChat.ts`:
  - Define a `MESSAGE_TIME_PART = "data-message-time"` constant.
  - Stamp the time when a message is created (user send + assistant finish) and
    attach it as a data-part on that message, the same way `withWorkTiming`
    appends `data-work-timing`.
  - These parts already persist for free: `saveChatThread` stores `parts`
    verbatim, so the timestamp survives reload with no schema change.
- Render in `Message.tsx`: a subtle muted timestamp under each bubble (read the
  `data-message-time` part; fall back to nothing if absent on old threads).
- Apply to both the global Chat (`chat.tsx`) and, for consistency, the Reader
  `ItemChat.tsx` (note: ItemChat is ephemeral, so its timestamps are
  session-only — acceptable).
- **No backend, no schema, no migration.**

Edge cases:
- Old saved threads have no `data-message-time` part → render nothing for those
  messages (graceful absence, like `WORK_TIMING_PART` today).
- The strip/linkify helpers ignore unknown data-parts already, so no conflict
  with citation marker handling.

### 3. Conversation search bar
**Client-side filter — decided approach.** `useChatThreads` already loads the
full list. Add a search input at the top of `ThreadList` (and the mobile
overlay) that filters by `title` + `preview`, case-insensitive.

- New small state in `ThreadList` (or lifted to `ThreadSidebar`) for the query.
- Filter `threads` before rendering; show a "No matches" empty state.
- Clears on new-chat / thread-open is optional (probably keep it sticky).
- **Known limitation (documented in UI or just accepted):** `preview` is only
  the first user message, so search won't match deep message content. Full-text
  search across all messages is a separate backend task (see backlog).
- No backend, no schema.

---

## Backlog — other "usual chat app" ideas (not building now)

Kept for a later pass. None are required for the three features above.

### Composer / input
- **Auto-growing textarea.** Today the composer is `rows=1` with a fixed
  `min-h`/`max-h` and `resize-none`, so multi-line input scrolls inside a
  one-line box instead of growing. Add JS auto-resize up to a max height.
  (Both `chat.tsx` and `ItemChat.tsx`.)
- **Per-thread draft persistence.** The pane is `key={activeId}` so switching
  threads remounts and discards typed-but-unsent input. Persist drafts per
  thread (e.g. a small Zustand map or sessionStorage).
- **Slash/command affordances** in the composer (optional).

### Conversation actions
- **Edit & resend a user message.** Only assistant "Regenerate" exists today;
  no way to edit a prior user turn and re-run from there.
- **Copy a single user message** and **export the whole conversation**
  (markdown). Copy currently only exists on assistant turns (`CopyButton` in
  `Message.tsx`).
- **Delete confirmation / undo.** `ThreadRow` deletes immediately with no
  confirm or undo.
- **Pin / favorite threads**; show **message count** in the sidebar
  (`message_count` is already returned by the API, just unrendered).

### Navigation / UX
- **Scroll-to-bottom button** when the user has scrolled up mid-stream.
  `useStickToBottom` exists but there's no jump affordance.
- **Chat keyboard shortcuts** — new chat, focus composer, next/prev thread.
  Global `useKeyboardShortcuts` currently has nothing chat-specific.
- **Thread-list pagination / infinite scroll.** The sidebar loads all threads
  in one request; fine for now, a problem at scale.

### Larger / backend work
- **Full-text conversation search.** A backend endpoint searching
  `chat_messages.parts` (FTS) so search matches deep message content, not just
  title + first-message preview. Replaces the client-side filter in feature 3
  when content search is wanted.
- **Reliable backend per-message timestamps.** If we ever want server-truth
  timestamps, `save_thread` must stop wiping `created_at` on every re-save
  (preserve existing rows' timestamps across upserts) and expose `created_at`
  in `ChatMessageModel`. Not needed for the client-side approach chosen above.
- **Share a conversation** (a `share_tokens` table already exists but is legacy/
  orphaned).
- **Token / cost usage display** per turn or per thread.
