import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import {
  Sparkles,
  ArrowUp,
  Square,
  SlidersHorizontal,
  MessageSquare,
  Plus,
  X,
  PanelLeft,
  MoreHorizontal,
  Pencil,
  Trash2,
  Check,
  AlertTriangle,
  RotateCw,
} from "lucide-react";
import { useAgentChat, type ChatFilters } from "@/hooks/useAgentChat";
import {
  saveChatThread,
  useChatThread,
  useChatThreads,
  useDeleteThread,
  useRenameThread,
  type ChatThreadSummary,
} from "@/hooks/useChatThreads";
import { useTags, useSourceTypes } from "@/hooks/useMeta";
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
import { Message } from "@/components/chat/Message";
import { keys } from "@/lib/queryKeys";
import { cn } from "@/lib/utils";

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
  const [fallbackId] = useState<string>(() => crypto.randomUUID());
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

  const openThread = (id: string) => {
    setParams({ thread: id });
    setSidebarOpen(false);
  };
  const newChat = () => {
    setParams({ thread: crypto.randomUUID() });
    setSidebarOpen(false);
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem-4rem)]">
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
        onNewChat={newChat}
        onOpenSidebar={() => setSidebarOpen(true)}
      />
    </div>
  );
}

/** Fetch the thread's stored messages, then mount the conversation seeded with
 * them. Gating on load keeps `useChat` seeding clean (initial messages are only
 * applied at mount). */
function ChatPane({
  threadId,
  onNewChat,
  onOpenSidebar,
}: {
  threadId: string;
  onNewChat: () => void;
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
      onNewChat={onNewChat}
      onOpenSidebar={onOpenSidebar}
    />
  );
}

function ChatConversation({
  threadId,
  initialMessages,
  onNewChat,
  onOpenSidebar,
}: {
  threadId: string;
  initialMessages: UIMessage[];
  onNewChat: () => void;
  onOpenSidebar: () => void;
}) {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState("");
  const [filters, setFilters] = useState<ChatFilters>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const sentPrefill = useRef(false);

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

  const { messages, status, isStreaming, error, send, regenerate, stop } =
    useAgentChat({ id: threadId, initialMessages, onFinish: persist });

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
      send(q, normalizeFilters(filters));
      const next = new URLSearchParams(params);
      next.delete("q");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll on new content.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const submit = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    send(q, normalizeFilters(filters));
    setInput("");
  };

  const isIdle = messages.length === 0;

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={onOpenSidebar}
            aria-label="Conversations"
          >
            <PanelLeft className="size-4" />
          </Button>
          <h1 className="text-[24px] font-semibold">Chat</h1>
        </div>
        <div className="flex items-center gap-2">
          {/* The sidebar owns "New chat" on desktop; surface it here only on
              mobile (where the sidebar is collapsed behind the panel toggle). */}
          {!isIdle && (
            <Button
              variant="ghost"
              size="sm"
              className="md:hidden"
              onClick={onNewChat}
              disabled={isStreaming}
            >
              <Plus className="size-3.5" /> New chat
            </Button>
          )}
          <FilterBar filters={filters} setFilters={setFilters} active={filtersActive} />
        </div>
      </div>

      {/* Messages */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          className={cn(
            "mx-auto max-w-3xl pb-6",
            isIdle ? "flex min-h-full flex-col justify-center" : "space-y-8",
          )}
        >
          {isIdle ? (
            <IdleState onPick={(q) => send(q, normalizeFilters(filters))} />
          ) : (
            messages.map((m, i) => (
              <Message
                key={m.id}
                message={m}
                isLast={i === messages.length - 1}
                isStreaming={isStreaming}
                onRegenerate={() => regenerate(normalizeFilters(filters))}
                onFollowup={(q) => send(q, normalizeFilters(filters))}
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
      <div className="border-t border-border pt-4">
        {filtersActive > 0 && (
          <ActiveFilterChips filters={filters} setFilters={setFilters} />
        )}
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask your library…"
            className="max-h-40 min-h-[44px] flex-1 resize-none rounded-[12px] border border-border bg-surface px-4 py-3 text-[14px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-border-strong"
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
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border pr-3 md:flex">
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Button variant="secondary" size="sm" className="mb-3 w-full justify-start" onClick={onNew}>
        <Plus className="size-3.5" /> New chat
      </Button>
      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-2 px-1 py-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : threads && threads.length > 0 ? (
          threads.map((t) => (
            <ThreadRow
              key={t.id}
              thread={t}
              active={t.id === activeId}
              onSelect={() => onSelect(t.id)}
              onDeleted={onNew}
            />
          ))
        ) : (
          <p className="px-2 py-6 text-center text-[12.5px] text-fg-subtle">
            No saved conversations yet.
          </p>
        )}
      </div>
    </div>
  );
}

function ThreadRow({
  thread,
  active,
  onSelect,
  onDeleted,
}: {
  thread: ChatThreadSummary;
  active: boolean;
  onSelect: () => void;
  onDeleted: () => void;
}) {
  const rename = useRenameThread();
  const del = useDeleteThread();
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
          className="min-w-0 flex-1 rounded-[8px] border border-border-strong bg-surface px-2 py-1 text-[13px] outline-none"
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
        className="min-w-0 flex-1 truncate py-2 text-left text-[13px] text-fg"
        title={label}
      >
        {label}
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
          <DropdownMenuItem
            onSelect={() => {
              setDraft(thread.title || "");
              setEditing(true);
            }}
          >
            <Pencil className="size-3.5" /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() =>
              del.mutate(thread.id, { onSuccess: () => active && onDeleted() })
            }
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
    <div className="mx-auto mb-2 flex max-w-3xl flex-wrap items-center gap-1.5">
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
