# Chat improvements — implementation progress

Companion to `docs/CHAT_IMPROVEMENTS_PLAN.md`. The plan's three "build now"
features (sidebar timestamps + date grouping, per-message timestamps, sidebar
search) were **already shipped** (commits `ceeaaf3`, `7e06295`). This pass
implements the **backlog** items the user selected:

- **Conversation actions** (edit/resend, copy user message, export conversation,
  delete-with-undo, pin/favorite + message count)
- **Navigation / UX** (scroll-to-bottom button, chat keyboard shortcuts)
- **Composer polish** (auto-growing textarea, per-thread draft persistence)
- **Auto-focus + toasts**
- **Code-block + citation UX** (code copy button, click-citation-to-scroll)
- **Streaming/scroll polish** (Esc to stop, auto-scroll on send)

Backend work was **explicitly out of scope** — everything here is frontend-only.

---

## Key design decisions

- **Delete-with-undo, no backend restore.** Delete optimistically removes the
  row from the `keys.chatThreads()` query cache and shows a 4s undo toast; the
  real `DELETE` API call is **deferred** ~4.5s. Undo cancels the timer and
  re-fetches (the thread was never actually deleted). This avoids needing to
  recreate server state. `deleteChatThread` is now exported from
  `useChatThreads.ts` for this.
- **Pin/favorite is frontend-only**, persisted in the `useUi` Zustand store
  (`pinnedThreads`, localStorage). Pinned threads render in a "Pinned" group at
  the top of the sidebar (when not searching). The plan noted pin "needs a tiny
  backend field" — we deliberately skipped backend and use client persistence.
- **Per-thread drafts are session-only** (`chatDrafts` map in `useUi`, NOT
  persisted) — they only need to survive thread-switch remounts, not reloads.
- **Citation chips now scroll instead of navigate.** Clicking an inline `[n]`
  chip smooth-scrolls to (and flashes) the matching Source card *within the same
  message* and no longer routes to the Reader. The Source card itself still
  links to the Reader. Anchor ids are per-message unique:
  `cite-<messageId>-<itemId>` via `citeAnchorId()`.
- **No syntax-highlighter dependency** added — code blocks get a styled header
  (language label) + hover copy button only.

---

## Done (files already edited in this pass)

1. **`web/src/hooks/useStickToBottom.ts`** — exposes `pinned` (render-visible
   mirror of the stick ref) and `scrollToBottom()`. Used for the jump-to-latest
   button and auto-scroll-on-send.
2. **`web/src/store/ui.ts`** — added `pinnedThreads` + `togglePin` (persisted),
   and `chatDrafts` + `setChatDraft`/`clearChatDraft` (session-only). `partialize`
   now also persists `pinnedThreads`.
3. **`web/src/components/common/AutoGrowTextarea.tsx`** — NEW. forwardRef
   textarea that grows to `scrollHeight`, capped by a `max-h-*` class.
4. **`web/src/hooks/useAgentChat.ts`** —
   - added `editAndResend(messageId, text, filters)` (truncates to before the
     edited turn, then sends) and returns it;
   - added `citeAnchorId(messageId, itemId)`;
   - **changed `linkifyCitationMarkers` signature** to
     `(text, citations, messageId)` — emits `#cite-<messageId>-<itemId>` hrefs.
5. **`web/src/components/common/Markdown.tsx`** — `#cite-` links now
   `preventDefault` + `flashCitation()` (scroll + replay `cite-flash`); fenced
   code renders through a `CodeBlock` with a language header + hover `CopyButton`.
   Dropped the now-redundant `[&_pre]` border/bg/rounded styles (CodeBlock owns
   the chrome).
6. **`web/src/styles/index.css`** — added `@keyframes cite-flash` + `.cite-flash`.
7. **`web/src/components/chat/CitationCard.tsx`** — accepts optional `messageId`;
   sets `id={citeAnchorId(...)}` + `scroll-mt-6` so chips can target it.
8. **`web/src/components/chat/Message.tsx`** —
   - new `onEdit?(id, text)` prop;
   - extracted `UserMessage` (hover copy + edit; edit swaps in an
     `AutoGrowTextarea`, Enter saves, Esc cancels, calls `onEdit`);
   - passes `message.id` to `linkifyCitationMarkers` and `CitationCard`;
   - imports `Pencil` + `AutoGrowTextarea`.
9. **`web/src/hooks/useChatThreads.ts`** — `deleteChatThread` is now exported.

---

## Done (continued — the wiring pass)

10. **`web/src/routes/chat.tsx`** — composer is now `AutoGrowTextarea` with a
    ref; auto-focus on mount + after send; per-thread drafts (seed from
    `useUi.getState().chatDrafts`, write on change, clear on send); a
    jump-to-latest button (shown when `!pinned && !isIdle`); `runSend` snaps to
    bottom + clears the draft; `onEdit` wired to `editAndResend`; Shift+Esc
    focuses the composer and bare Esc stops a live stream; an "Export as
    Markdown" header action; the `useChatShortcuts` hook (⌘/Ctrl+Shift+O new
    chat, ⌘/Ctrl+Shift+↑/↓ prev/next thread); sidebar "Pinned" group +
    pin/unpin + `message_count`; optimistic delete-with-undo toast.
11. **`web/src/components/chat/ItemChat.tsx`** — same composer polish
    (`AutoGrowTextarea`, auto-focus, jump-to-latest, `runSend`) + `onEdit` wired
    to `editAndResend`.

**Verification:** `npm run typecheck`, `npm run lint`, `npm run build` all pass
clean. Visual/Playwright verification NOT yet done (needs the API + a live LLM
backend for real chat turns).

---

## ~~Remaining~~ (DONE — kept for reference)

### A. `web/src/routes/chat.tsx` (the bulk of the wiring)
- **Composer:** replace the `<textarea>` with `<AutoGrowTextarea>`; add a
  `composerRef`; auto-focus on mount (thread open / new chat remounts the pane)
  and re-focus after send.
- **Draft persistence:** seed `input` from `useUi`'s `chatDrafts[threadId]` on
  mount; write to `setChatDraft(threadId, ...)` on change; `clearChatDraft` on
  successful send.
- **Scroll-to-bottom button:** consume `pinned` + `scrollToBottom` from
  `useStickToBottom`; show a floating "jump to latest" button above the composer
  when `!pinned && !isIdle`; call `scrollToBottom()` from `submit`/`send`.
- **Edit/resend:** pass `onEdit={(id, text) => editAndResend(id, text, normalizeFilters(filters))}`
  to `<Message>` (pull `editAndResend` out of `useAgentChat`).
- **Export conversation (markdown):** add a header action (e.g. a
  `DropdownMenu` with "Export as Markdown" — only when messages exist) that
  builds markdown (`**You:** … / **Merlin:** …`, joined by `---`, run through
  `stripCitationMarkers`), downloads a `.md` Blob, and fires a success `toast`.
- **Keyboard shortcuts** (chat-route level; gate on `metaKey/ctrlKey` so the
  global `useKeyboardShortcuts`, which early-returns on modifiers, doesn't
  conflict):
  - ⌘/Ctrl+Shift+O → new chat
  - ⌘/Ctrl+Shift+↑ / ↓ → previous / next thread (use the `useChatThreads` list +
    `openThread`)
  - Shift+Esc → focus composer; Esc → stop streaming (composer/pane level)
- **Sidebar (`ThreadList` / `ThreadRow`):**
  - "Pinned" group at top (when not searching) from `useUi().pinnedThreads`;
    pinned ids excluded from the date buckets.
  - Pin/Unpin item in the row `DropdownMenu` + a pin indicator on pinned rows
    (lucide `Pin` / `PinOff`).
  - Render `message_count` subtly in the row (already on `ChatThreadSummary`).
  - Replace immediate `useDeleteThread().mutate` with the **optimistic
    delete-with-undo** flow (lift to `ThreadList`: `useQueryClient` cache removal
    + deferred `deleteChatThread` + undo `toast`). Remove the now-unused
    `useDeleteThread` import if nothing else uses it.
  - Imports needed: `toast` from `@/components/ui/toaster`, `useUi`,
    `deleteChatThread`, `Pin`/`PinOff`/`Download` icons.

### B. `web/src/components/chat/ItemChat.tsx`
- Use `<AutoGrowTextarea>`; auto-focus on mount.
- Add the scroll-to-bottom button (it already uses `useStickToBottom`).
- Pass `onEdit={(id, text) => editAndResend(id, text, filters)}` to `<Message>`
  (pull `editAndResend` from its `useAgentChat`).

### C. Verify (task #5)
- `cd web && npm run typecheck && npm run lint && npm run build`.
- Watch for: the `linkifyCitationMarkers` signature change (only caller is
  `Message.tsx`, already updated — grep to be sure), and any test referencing it.
- Optionally screenshot (Playwright, desktop + mobile) per CLAUDE.md.

---

## Open follow-ups / notes
- Undo after deleting the *active* thread restores the row but doesn't re-open
  it (URL already moved to a new chat) — acceptable.
- If the page reloads inside the ~4.5s delete window, the deferred DELETE is lost
  and the thread survives (effectively an undo) — acceptable.
- Slash/command affordances in the composer are still backlog (not in scope).
