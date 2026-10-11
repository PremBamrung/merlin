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
  X,
  MoreHorizontal,
  AlertTriangle,
  RotateCw,
  Download,
} from "lucide-react";
import {
  useAgentChat,
  latestUsage,
  stripCitationMarkers,
  type ChatFilters,
} from "@/hooks/useAgentChat";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import {
  saveChatThread,
  useChatThread,
  useChatThreads,
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
import { Message } from "@/components/chat/Message";
import { ThreadList } from "@/components/chat/ThreadList";
import { PanelSlot } from "@/components/layout/panel";
import { ContextMeter } from "@/components/chat/UsageFooter";
import { AutoGrowTextarea } from "@/components/common/AutoGrowTextarea";
import { toast } from "@/components/ui/toaster";
import { keys } from "@/lib/queryKeys";
import { cn, randomId } from "@/lib/utils";

const STARTERS = [
  "What are the recurring themes across my library?",
  "Summarize what I've saved about AI agents.",
  "Which videos discuss business strategy?",
];

/**
 * The Chat place. The thread list (continuable, persisted server-side) lives in
 * the context panel; the active conversation is the main view. The active thread lives in
 * `?thread=<id>`; the conversation pane is keyed by it so switching threads
 * remounts a fresh `useChat` seeded from the thread's stored history.
 *
 * Persistence is client-driven: each finished turn PUTs the full message list
 * (parts verbatim, citations intact) — see useChatThreads + the chat router.
 */
export default function ChatRoute() {
  const [params, setParams] = useSearchParams();

  // The active thread id always exists: from the URL, or a fresh client id for
  // a new conversation (the thread row is created lazily on its first turn, so
  // no empty threads accumulate).
  const [fallbackId] = useState<string>(() => randomId());
  const activeId = params.get("thread") ?? fallbackId;

  // Canonicalise the URL so a refresh keeps the same thread and the sidebar can
  // highlight it — without clobbering a `?q=` prefill from the command palette.
  useEffect(() => {
    if (!params.get("thread")) {
      const next = new URLSearchParams(params);
      next.set("thread", activeId);
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openThread = useCallback(
    (id: string) => setParams({ thread: id }),
    [setParams],
  );
  const newChat = useCallback(() => setParams({ thread: randomId() }), [setParams]);

  // The panel's list also powers next/prev-thread shortcuts (shared query cache).
  const { data: threadList } = useChatThreads();
  useChatShortcuts({ threads: threadList, activeId, onNew: newChat, onSelect: openThread });
  const n = threadList?.length ?? 0;

  return (
    <div className="flex h-full min-h-0">
      <PanelSlot title="Chats" sub={threadList ? `${n} conversation${n === 1 ? "" : "s"}` : undefined}>
        <ThreadList activeId={activeId} onSelect={openThread} onNew={newChat} />
      </PanelSlot>
      <ChatPane key={activeId} threadId={activeId} />
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
function ChatPane({ threadId }: { threadId: string }) {
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
    />
  );
}

function ChatConversation({
  threadId,
  initialMessages,
}: {
  threadId: string;
  initialMessages: UIMessage[];
}) {
  const qc = useQueryClient();
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

  // Stable per-message handlers so the memoized <Message> rows don't re-render on
  // every streamed token. `nf` only changes when the FilterBar changes.
  const nf = useMemo(() => normalizeFilters(filters), [filters]);
  const handleRegenerate = useCallback(() => {
    regenerate(nf);
    scrollToBottom();
  }, [regenerate, nf, scrollToBottom]);
  const handleEdit = useCallback(
    (id: string, text: string) => {
      editAndResend(id, text, nf);
      clearChatDraft(threadId);
      scrollToBottom();
    },
    [editAndResend, nf, clearChatDraft, threadId, scrollToBottom],
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

  // Prefill from ?q= (the command palette's "Ask:" action) — auto-send once on a
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
      {/* Header: only the chat's own controls. Navigation is the rail (or the
          tabs on phones) and the thread list is the context panel. */}
      <div className="flex items-center justify-end gap-2 px-4 py-2.5 md:px-6 md:py-4">
        <div className="flex items-center gap-2">
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
                onRegenerate={handleRegenerate}
                onFollowup={runSend}
                onEdit={handleEdit}
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
        {!isIdle && (
          <div className="mb-1.5 flex justify-end px-1">
            <ContextMeter usage={latestUsage(messages)} />
          </div>
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
    <div className="rounded-[12px] border border-fail/40 bg-fail/10 px-4 py-3">
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fail" />
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
        "inline-flex items-center gap-1 rounded-full border border-ui-toggle-on-border bg-ui-toggle-on-bg px-2.5 py-1 text-[11px] text-ui-toggle-on-fg",
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
      <div className="flex size-12 items-center justify-center rounded-full bg-ui-tint-bg text-ui-icon">
        <MessageSquare className="size-6" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <p className="font-display text-[18px] font-semibold">Ask your library</p>
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
            <Sparkles className="size-4 shrink-0 text-fg-subtle group-hover:text-ui-icon" />
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
            <span className="ml-1 flex size-4 items-center justify-center rounded-full bg-ui-primary font-mono text-[10px] text-ui-primary-fg">
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
                      ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
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
                        ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
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
