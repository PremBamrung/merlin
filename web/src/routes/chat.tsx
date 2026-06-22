import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import {
  Sparkles,
  ArrowUp,
  ArrowDown,
  Square,
  SlidersHorizontal,
  MessageSquare,
  Plus,
  X,
  Menu,
  PanelLeft,
  MoreHorizontal,
  Pencil,
  Trash2,
  Check,
  AlertTriangle,
  RotateCw,
  Search,
  Pin,
  PinOff,
  Download,
} from "lucide-react";
import { useAgentChat, stripCitationMarkers, type ChatFilters } from "@/hooks/useAgentChat";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import {
  saveChatThread,
  deleteChatThread,
  useChatThread,
  useChatThreads,
  useRenameThread,
  type ChatThreadSummary,
} from "@/hooks/useChatThreads";
import { useTags, useSourceTypes } from "@/hooks/useMeta";
import { useUi } from "@/store/ui";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Message } from "@/components/chat/Message";
import { AutoGrowTextarea } from "@/components/common/AutoGrowTextarea";
import { toast } from "@/components/ui/toaster";
import { keys } from "@/lib/queryKeys";
import { relDate } from "@/lib/format";
import { cn, randomId } from "@/lib/utils";

const STARTERS = [
  "What are the recurring themes across my library?",
  "Summarize what I've saved about AI agents.",
  "Which videos discuss business strategy?",
];

/**
 * The Chat tab. A ChatGPT-style thread sidebar (continuable, persisted
 * server-side) alongside the active conversation. The active thread lives in
 * `?thread=<id>`; the conversation pane is keyed by it so switching threads
 * remounts a fresh `useChat` seeded from the thread's stored history.
 *
 * Persistence is client-driven: each finished turn PUTs the full message list
 * (parts verbatim, citations intact) — see useChatThreads + the chat router.
 */
export default function ChatRoute() {
  const [params, setParams] = useSearchParams();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // The active thread id always exists: from the URL, or a fresh client id for
  // a new conversation (the thread row is created lazily on its first turn, so
  // no empty threads accumulate).
  const [fallbackId] = useState<string>(() => randomId());
  const activeId = params.get("thread") ?? fallbackId;

  // Canonicalise the URL so a refresh keeps the same thread and the sidebar can
  // highlight it — without clobbering a `?q=` prefill from the Today omnibox.
  useEffect(() => {
    if (!params.get("thread")) {
      const next = new URLSearchParams(params);
      next.set("thread", activeId);
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openThread = useCallback(
    (id: string) => {
      setParams({ thread: id });
      setSidebarOpen(false);
    },
    [setParams],
  );
  const newChat = useCallback(() => {
    setParams({ thread: randomId() });
    setSidebarOpen(false);
  }, [setParams]);

  // The sidebar list also powers next/prev-thread shortcuts (shared query cache).
  const { data: threadList } = useChatThreads();
  useChatShortcuts({ threads: threadList, activeId, onNew: newChat, onSelect: openThread });

  return (
    <div className="flex h-full min-h-0">
      <ThreadSidebar
        activeId={activeId}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSelect={openThread}
        onNew={newChat}
      />
      <ChatPane
        key={activeId}
        threadId={activeId}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
    </div>
  );
}

/**
 * Chat-route keyboard shortcuts. Modifier-gated (⌘/Ctrl+Shift) so they coexist
 * with the global g-prefix nav (which early-returns on modifiers) and still fire
 * while the composer is focused:
 *   ⌘/Ctrl+Shift+O      → new chat
 *   ⌘/Ctrl+Shift+↑ / ↓  → previous / next thread
 */
function useChatShortcuts({
  threads,
  activeId,
  onNew,
  onSelect,
}: {
  threads: ChatThreadSummary[] | undefined;
  activeId: string;
  onNew: () => void;
  onSelect: (id: string) => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || !e.shiftKey) return;
      if (e.key.toLowerCase() === "o") {
        e.preventDefault();
        onNew();
        return;
      }
      if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        if (!threads || threads.length === 0) return;
        e.preventDefault();
        const idx = threads.findIndex((t) => t.id === activeId);
        // From an unsaved/new thread (not in the list) either arrow lands on the
        // newest thread; otherwise step within bounds.
        const next =
          idx < 0
            ? 0
            : Math.min(threads.length - 1, Math.max(0, idx + (e.key === "ArrowUp" ? -1 : 1)));
        const target = threads[next];
        if (target && target.id !== activeId) onSelect(target.id);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [threads, activeId, onNew, onSelect]);
}

/** Fetch the thread's stored messages, then mount the conversation seeded with
 * them. Gating on load keeps `useChat` seeding clean (initial messages are only
 * applied at mount). */
function ChatPane({
  threadId,
  onOpenSidebar,
}: {
  threadId: string;
  onOpenSidebar: () => void;
}) {
  const { data, isLoading } = useChatThread(threadId);

  if (isLoading || !data) {
    return (
      <div className="flex min-w-0 flex-1 flex-col gap-4 p-6">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-20 w-full max-w-3xl" />
        <Skeleton className="h-20 w-full max-w-3xl" />
      </div>
    );
  }

  return (
    <ChatConversation
      threadId={threadId}
      initialMessages={data.messages as unknown as UIMessage[]}
      onOpenSidebar={onOpenSidebar}
    />
  );
}

function ChatConversation({
  threadId,
  initialMessages,
  onOpenSidebar,
}: {
  threadId: string;
  initialMessages: UIMessage[];
  onOpenSidebar: () => void;
}) {
  const qc = useQueryClient();
  const openAdd = useUi((s) => s.openAdd);
  const setNavOpen = useUi((s) => s.setNavOpen);
  const setChatDraft = useUi((s) => s.setChatDraft);
  const clearChatDraft = useUi((s) => s.clearChatDraft);
  const [params, setParams] = useSearchParams();
  // Seed the composer from any saved draft for this thread (the pane remounts on
  // thread switch, so local state alone would drop unsent input). Read once at
  // mount via getState to avoid subscribing the whole pane to the draft map.
  const [input, setInput] = useState(() => useUi.getState().chatDrafts[threadId] ?? "");
  const [filters, setFilters] = useState<ChatFilters>({});
  const sentPrefill = useRef(false);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const onInputChange = (value: string) => {
    setInput(value);
    setChatDraft(threadId, value);
  };

  // Client-driven persistence — best-effort; a failed write must never disrupt
  // the chat. Save the current message list, then refresh the sidebar (which
  // surfaces the freshly-titled thread).
  const persist = useCallback(
    (msgs: UIMessage[]) => {
      if (!msgs.length) return;
      saveChatThread(threadId, msgs)
        .then(() => qc.invalidateQueries({ queryKey: keys.chatThreads() }))
        .catch(() => {});
    },
    [threadId, qc],
  );

  const { messages, status, isStreaming, error, send, regenerate, editAndResend, stop } =
    useAgentChat({ id: threadId, initialMessages, onFinish: persist });

  // Follow the stream to the bottom only while the user is already pinned there,
  // so scrolling up to re-read isn't interrupted by incoming tokens. `pinned`
  // drives the jump-to-latest button; `scrollToBottom` re-engages it.
  const { scrollRef, bottomRef, pinned, scrollToBottom } = useStickToBottom(messages);

  // Send + always snap to the latest turn (a send is an explicit "go to bottom"
  // intent even if the user had scrolled up). Clears the saved draft.
  const runSend = useCallback(
    (q: string) => {
      send(q, normalizeFilters(filters));
      clearChatDraft(threadId);
      scrollToBottom();
    },
    [send, filters, clearChatDraft, threadId, scrollToBottom],
  );

  // Auto-focus the composer when the pane mounts (new chat / thread open).
  useEffect(() => {
    composerRef.current?.focus();
  }, []);

  // Shift+Esc focuses the composer from anywhere; bare Esc stops a live stream.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (e.shiftKey) {
        e.preventDefault();
        composerRef.current?.focus();
      } else if (isStreaming) {
        e.preventDefault();
        stop();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isStreaming, stop]);

  // Persist as soon as a turn STARTS (status flips to "submitted"), not just at
  // the end — so the thread + the user's message are saved immediately and the
  // title is generated from that first message, surviving a slow/failed answer.
  useEffect(() => {
    if (status === "submitted") persist(messages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const filtersActive =
    (filters.source_types?.length ?? 0) + (filters.tags?.length ?? 0);

  // Prefill from ?q= (Today omnibox / command palette) — auto-send once on a
  // fresh thread, then strip q while keeping the thread id.
  useEffect(() => {
    const q = params.get("q");
    if (q && !sentPrefill.current && messages.length === 0) {
      sentPrefill.current = true;
      runSend(q);
      const next = new URLSearchParams(params);
      next.delete("q");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    runSend(q);
    setInput("");
    composerRef.current?.focus();
  };

  const isIdle = messages.length === 0;

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Header. On desktop the global topbar already shows the "Chat" title, so
          this row carries only Filters. On mobile the topbar is hidden, so this
          row also owns the title + the panel/new-chat/add-source controls. */}
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5 md:border-0 md:px-6 md:py-4">
        <div className="flex items-center gap-1 md:hidden">
          {/* App nav (Today/Feed/…) — the global topbar that normally hosts this
              hamburger is hidden on the Chat route on mobile. */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </Button>
          {/* Conversations (this chat's thread list). */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpenSidebar}
            aria-label="Conversations"
          >
            <PanelLeft className="size-4" />
          </Button>
          <h1 className="text-[17px] font-semibold">Chat</h1>
        </div>
        <div className="flex items-center gap-2 md:ml-auto">
          <FilterBar filters={filters} setFilters={setFilters} active={filtersActive} />
          {!isIdle && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="icon-sm" aria-label="Conversation actions">
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => exportConversation(messages)}>
                  <Download className="size-3.5" /> Export as Markdown
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {/* Add-source lives in the global topbar, which is hidden on mobile for
              this route — surface it here so it stays reachable. */}
          <Button
            size="icon"
            className="md:hidden"
            onClick={() => openAdd()}
            aria-label="Add source"
          >
            <Plus className="size-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div
          className={cn(
            "w-full px-4 pb-6 sm:px-6",
            isIdle ? "flex min-h-full flex-col justify-center" : "space-y-8",
          )}
        >
          {isIdle ? (
            <IdleState onPick={runSend} />
          ) : (
            messages.map((m, i) => (
              <Message
                key={m.id}
                message={m}
                isLast={i === messages.length - 1}
                isStreaming={isStreaming}
                onRegenerate={() => {
                  regenerate(normalizeFilters(filters));
                  scrollToBottom();
                }}
                onFollowup={runSend}
                onEdit={(id, text) => {
                  editAndResend(id, text, normalizeFilters(filters));
                  clearChatDraft(threadId);
                  scrollToBottom();
                }}
              />
            ))
          )}
          {error && !isStreaming && (
            <ChatError error={error} onRetry={() => regenerate(normalizeFilters(filters))} />
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="relative border-t border-border px-4 py-3 sm:px-6 sm:py-4">
        {/* Jump-to-latest — only while reading above the fold mid-conversation. */}
        {!pinned && !isIdle && (
          <button
            onClick={scrollToBottom}
            aria-label="Jump to latest"
            className="absolute -top-5 left-1/2 z-10 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-surface-2 text-fg-muted shadow-lg shadow-black/30 transition-colors hover:text-fg"
          >
            <ArrowDown className="size-4" />
          </button>
        )}
        {filtersActive > 0 && (
          <ActiveFilterChips filters={filters} setFilters={setFilters} />
        )}
        <div className="flex w-full items-end gap-2">
          <AutoGrowTextarea
            ref={composerRef}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask your library…"
            className="max-h-40 min-h-[44px] flex-1 rounded-[12px] border border-border bg-surface px-4 py-3 text-[16px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-border-strong sm:text-[14px]"
          />
          {isStreaming ? (
            <Button onClick={stop} variant="secondary" size="icon" className="size-11 rounded-[12px]">
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              onClick={submit}
              disabled={!input.trim()}
              size="icon"
              className="size-11 rounded-[12px]"
            >
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Thread sidebar
// --------------------------------------------------------------------------- //

function ThreadSidebar({
  activeId,
  open,
  onClose,
  onSelect,
  onNew,
}: {
  activeId: string;
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <>
      {/* Desktop: a static left column. */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border py-4 pl-4 pr-3 md:flex">
        <ThreadList activeId={activeId} onSelect={onSelect} onNew={onNew} />
      </aside>

      {/* Mobile: a slide-in overlay. */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={onClose} />
          <div className="absolute left-0 top-0 h-full w-72 max-w-[80%] bg-bg p-4 shadow-xl">
            <div className="mb-2 flex items-center justify-between">
              <span className="eyebrow">Conversations</span>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
                <X className="size-4" />
              </Button>
            </div>
            <ThreadList activeId={activeId} onSelect={onSelect} onNew={onNew} />
          </div>
        </div>
      )}
    </>
  );
}

// Sidebar date buckets, in display order. Threads arrive newest-first (the API
// orders by updated_at desc), so iterating in order keeps each bucket sorted.
const BUCKETS = ["Today", "Yesterday", "Previous 7 Days", "Older"] as const;

function bucketOf(iso: string | null): (typeof BUCKETS)[number] {
  if (!iso) return "Older";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "Older";
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round(
    (startOfDay(new Date()).getTime() - startOfDay(dt).getTime()) / 86_400_000,
  );
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 Days";
  return "Older";
}

function ThreadList({
  activeId,
  onSelect,
  onNew,
}: {
  activeId: string;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const { data: threads, isLoading } = useChatThreads();
  const qc = useQueryClient();
  const pinnedThreads = useUi((s) => s.pinnedThreads);
  const togglePin = useUi((s) => s.togglePin);
  const pinnedSet = useMemo(() => new Set(pinnedThreads), [pinnedThreads]);
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  // Optimistic delete with an undo window: drop the row immediately, defer the
  // real DELETE, and let Undo cancel it (the thread was never actually removed,
  // so undo just re-fetches). No backend "restore" needed. Timers outlive an
  // unmount on purpose, so the delete still fires if the user navigates away.
  const pendingDeletes = useRef<Map<string, number>>(new Map());
  const deleteThread = useCallback(
    (id: string) => {
      qc.setQueryData<ChatThreadSummary[]>(keys.chatThreads(), (cur) =>
        (cur ?? []).filter((t) => t.id !== id),
      );
      if (id === activeId) onNew();
      const timer = window.setTimeout(() => {
        pendingDeletes.current.delete(id);
        deleteChatThread(id)
          .catch(() => {})
          .finally(() => qc.invalidateQueries({ queryKey: keys.chatThreads() }));
      }, 4500);
      pendingDeletes.current.set(id, timer);
      toast("Conversation deleted", {
        duration: 4000,
        action: {
          label: "Undo",
          onClick: () => {
            const t = pendingDeletes.current.get(id);
            if (t) {
              window.clearTimeout(t);
              pendingDeletes.current.delete(id);
            }
            qc.invalidateQueries({ queryKey: keys.chatThreads() });
          },
        },
      });
    },
    [qc, activeId, onNew],
  );

  // Client-side filter over title + first-message preview (the only text the
  // list endpoint returns; deep message content isn't searched).
  const filtered = useMemo(() => {
    if (!threads) return [];
    if (!q) return threads;
    return threads.filter(
      (t) =>
        (t.title ?? "").toLowerCase().includes(q) ||
        (t.preview ?? "").toLowerCase().includes(q),
    );
  }, [threads, q]);

  // Grouped by date bucket, with pinned threads lifted into a "Pinned" group at
  // the top — but a search shows a flat result list instead.
  const groups = useMemo(() => {
    if (q) return [];
    const out: (readonly [string, ChatThreadSummary[]])[] = [];
    const pinned = filtered.filter((t) => pinnedSet.has(t.id));
    if (pinned.length) out.push(["Pinned", pinned] as const);
    const map = new Map<string, ChatThreadSummary[]>();
    for (const t of filtered) {
      if (pinnedSet.has(t.id)) continue;
      const b = bucketOf(t.updated_at);
      (map.get(b) ?? map.set(b, []).get(b)!).push(t);
    }
    for (const b of BUCKETS) if (map.has(b)) out.push([b, map.get(b)!] as const);
    return out;
  }, [filtered, q, pinnedSet]);

  const row = (t: ChatThreadSummary) => (
    <ThreadRow
      key={t.id}
      thread={t}
      active={t.id === activeId}
      pinned={pinnedSet.has(t.id)}
      onSelect={() => onSelect(t.id)}
      onPin={() => togglePin(t.id)}
      onDelete={() => deleteThread(t.id)}
    />
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Button variant="secondary" size="sm" className="mb-2 w-full justify-start" onClick={onNew}>
        <Plus className="size-3.5" /> New chat
      </Button>

      <div className="relative mb-2">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search conversations…"
          className="h-8 pl-8 text-[13px]"
          aria-label="Search conversations"
        />
      </div>

      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 px-1 py-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : !threads || threads.length === 0 ? (
          <p className="px-2 py-6 text-center text-[12.5px] text-fg-subtle">
            No saved conversations yet.
          </p>
        ) : filtered.length === 0 ? (
          <p className="px-2 py-6 text-center text-[12.5px] text-fg-subtle">
            No conversations match “{query.trim()}”.
          </p>
        ) : q ? (
          filtered.map(row)
        ) : (
          groups.map(([label, items]) => (
            <div key={label} className="pb-1">
              <p className="eyebrow px-2.5 pb-1 pt-2 text-fg-subtle">{label}</p>
              {items.map(row)}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ThreadRow({
  thread,
  active,
  pinned,
  onSelect,
  onPin,
  onDelete,
}: {
  thread: ChatThreadSummary;
  active: boolean;
  pinned: boolean;
  onSelect: () => void;
  onPin: () => void;
  onDelete: () => void;
}) {
  const rename = useRenameThread();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  const label = thread.title || thread.preview || "New conversation";

  const commitRename = () => {
    const title = draft.trim();
    if (title && title !== thread.title) rename.mutate({ id: thread.id, title });
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1 px-1.5 py-1">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commitRename();
            if (e.key === "Escape") setEditing(false);
          }}
          onBlur={commitRename}
          className="min-w-0 flex-1 rounded-[8px] border border-border-strong bg-surface px-2 py-1 text-[16px] outline-none sm:text-[13px]"
        />
        <Button variant="ghost" size="icon" className="size-7" onClick={commitRename}>
          <Check className="size-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group flex items-center gap-1 rounded-[8px] pl-2.5 pr-1 transition-colors",
        active ? "bg-surface-2" : "hover:bg-surface-2/60",
      )}
    >
      <button
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-1.5 py-2 text-left"
        title={label}
      >
        {pinned && <Pin className="size-3 shrink-0 text-fg-subtle" />}
        <span className="min-w-0 flex-1 truncate text-[13px] text-fg">{label}</span>
        <span className="shrink-0 text-[11px] text-fg-subtle">
          {relDate(thread.updated_at)}
          {thread.message_count > 0 && (
            <span className="tabular-nums"> · {thread.message_count}</span>
          )}
        </span>
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className="shrink-0 rounded-[6px] p-1 text-fg-subtle opacity-0 transition-opacity hover:text-fg group-hover:opacity-100 data-[state=open]:opacity-100"
            aria-label="Conversation options"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={onPin}>
            {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
            {pinned ? "Unpin" : "Pin"}
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setDraft(thread.title || "");
              setEditing(true);
            }}
          >
            <Pencil className="size-3.5" /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={onDelete}
            className="text-accent focus:text-accent"
          >
            <Trash2 className="size-3.5" /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function normalizeFilters(f: ChatFilters): ChatFilters {
  return {
    source_types: f.source_types?.length ? f.source_types : null,
    tags: f.tags?.length ? f.tags : null,
  };
}

/** Render the conversation as plain markdown (`**You:** … / **Merlin:** …`),
 * citation markers stripped, turns separated by rules. */
function conversationToMarkdown(messages: UIMessage[]): string {
  return messages
    .map((m) => {
      const text = stripCitationMarkers(
        (m.parts ?? [])
          .filter((p) => (p as { type: string }).type === "text")
          .map((p) => (p as { text?: string }).text ?? "")
          .join(""),
      ).trim();
      if (!text) return "";
      return `**${m.role === "user" ? "You" : "Merlin"}:**\n\n${text}`;
    })
    .filter(Boolean)
    .join("\n\n---\n\n");
}

/** Download the conversation as a `.md` file. */
function exportConversation(messages: UIMessage[]): void {
  const md = conversationToMarkdown(messages);
  if (!md) return;
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `merlin-chat-${new Date().toISOString().slice(0, 10)}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast("Conversation exported");
}

/** Surfaces a failed/interrupted turn (e.g. the agent hit its per-turn step cap
 * — `chat_max_requests` — searching without settling). Without this the turn
 * just stops on its tool traces with no answer, which reads as "stuck". */
function ChatError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const msg = error?.message ?? "";
  const isLimit = /request[_ ]?limit|usage limit|exceeded|step/i.test(msg);
  return (
    <div className="rounded-[12px] border border-accent-border bg-accent-subtle/40 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-accent" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-[13.5px] font-medium text-fg">
            {isLimit
              ? "Merlin reached its step limit for this answer."
              : "This answer was interrupted."}
          </p>
          <p className="text-[12.5px] leading-relaxed text-fg-muted">
            {isLimit
              ? "It searched several times without settling on an answer — often a sign the library doesn't cover this. Try rephrasing or narrowing with filters (or raise CHAT_MAX_REQUESTS)."
              : msg || "Something went wrong while generating the response."}
          </p>
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[12px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
          >
            <RotateCw className="size-3.5" /> Retry
          </button>
        </div>
      </div>
    </div>
  );
}

/** Active chat filters as removable chips, shown above the composer. */
function ActiveFilterChips({
  filters,
  setFilters,
}: {
  filters: ChatFilters;
  setFilters: (f: ChatFilters) => void;
}) {
  const sources = filters.source_types ?? [];
  const tags = filters.tags ?? [];
  const removeSource = (name: string) =>
    setFilters({ ...filters, source_types: sources.filter((x) => x !== name) });
  const removeTag = (name: string) =>
    setFilters({ ...filters, tags: tags.filter((x) => x !== name) });

  return (
    <div className="mb-2 flex w-full flex-wrap items-center gap-1.5">
      <span className="eyebrow text-fg-subtle">Filtered to</span>
      {sources.map((s) => (
        <Chip key={`s-${s}`} onRemove={() => removeSource(s)} className="capitalize">
          {s}
        </Chip>
      ))}
      {tags.map((t) => (
        <Chip key={`t-${t}`} onRemove={() => removeTag(t)} mono>
          #{t}
        </Chip>
      ))}
      <button
        onClick={() => setFilters({})}
        className="text-[12px] text-fg-subtle underline-offset-2 hover:text-fg hover:underline"
      >
        Clear
      </button>
    </div>
  );
}

function Chip({
  children,
  onRemove,
  mono,
  className,
}: {
  children: React.ReactNode;
  onRemove: () => void;
  mono?: boolean;
  className?: string;
}) {
  return (
    <button
      onClick={onRemove}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-accent-border bg-accent-subtle px-2.5 py-1 text-[11px] text-accent",
        mono && "font-mono",
        className,
      )}
    >
      {children} <X className="size-3" />
    </button>
  );
}

function IdleState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-accent-subtle text-accent">
        <MessageSquare className="size-6" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <p className="text-[18px] font-semibold">Ask your library</p>
        <p className="text-[14px] text-fg-muted">
          Merlin answers from everything you've saved, with citations.
        </p>
      </div>
      <div className="flex w-full max-w-lg flex-col gap-2">
        {STARTERS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="group flex items-center gap-2.5 rounded-[10px] border border-border bg-surface px-4 py-3 text-left text-[13.5px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
          >
            <Sparkles className="size-4 shrink-0 text-fg-subtle group-hover:text-accent" />
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function FilterBar({
  filters,
  setFilters,
  active,
}: {
  filters: ChatFilters;
  setFilters: (f: ChatFilters) => void;
  active: number;
}) {
  const tags = useTags();
  const sourceTypes = useSourceTypes();
  const topTags = useMemo(() => (tags.data ?? []).slice(0, 20), [tags.data]);

  const toggleSource = (name: string) => {
    const cur = filters.source_types ?? [];
    setFilters({
      ...filters,
      source_types: cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name],
    });
  };
  const toggleTag = (name: string) => {
    const cur = filters.tags ?? [];
    setFilters({
      ...filters,
      tags: cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name],
    });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm">
          <SlidersHorizontal className="size-3.5" /> Filters
          {active > 0 && (
            <span className="ml-1 flex size-4 items-center justify-center rounded-full bg-accent font-mono text-[10px] text-accent-fg">
              {active}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-4">
        <div className="space-y-2">
          <p className="eyebrow">Source types</p>
          <div className="flex flex-wrap gap-1.5">
            {(sourceTypes.data ?? []).map((s) => {
              const on = (filters.source_types ?? []).includes(s.name);
              return (
                <button
                  key={s.name}
                  onClick={() => toggleSource(s.name)}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-[12px] capitalize transition-colors",
                    on
                      ? "border-accent-border bg-accent-subtle text-accent"
                      : "border-border text-fg-muted hover:border-border-strong",
                  )}
                >
                  {s.name}
                </button>
              );
            })}
          </div>
        </div>

        {topTags.length > 0 && (
          <div className="space-y-2">
            <p className="eyebrow">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {topTags.map((t) => {
                const on = (filters.tags ?? []).includes(t.name);
                return (
                  <button
                    key={t.name}
                    onClick={() => toggleTag(t.name)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 font-mono text-[11px] transition-colors",
                      on
                        ? "border-accent-border bg-accent-subtle text-accent"
                        : "border-border text-fg-subtle hover:border-border-strong",
                    )}
                  >
                    #{t.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {active > 0 && (
          <button
            onClick={() => setFilters({})}
            className="text-[12px] text-fg-subtle underline-offset-2 hover:text-fg hover:underline"
          >
            Clear all filters
          </button>
        )}
      </PopoverContent>
    </Popover>
  );
}
