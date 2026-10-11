import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import {
  Sparkles,
  ArrowDown,
  MoreHorizontal,
  AlertTriangle,
  RotateCw,
  Download,
  Plus,
} from "lucide-react";
import {
  useAgentChat,
  latestUsage,
  stripCitationMarkers,
  CITATIONS_PART,
  type ChatFilters,
} from "@/hooks/useAgentChat";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import {
  saveChatThread,
  useChatThread,
  useChatThreads,
  type ChatThreadSummary,
} from "@/hooks/useChatThreads";
import { useUi } from "@/store/ui";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Mark } from "@/components/brand/Mark";
import { Composer } from "@/components/chat/Composer";
import { Message } from "@/components/chat/Message";
import { ThreadList } from "@/components/chat/ThreadList";
import { PanelSlot } from "@/components/layout/panel";
import { ContextMeter } from "@/components/chat/UsageFooter";
import { toast } from "@/components/ui/toaster";
import { keys } from "@/lib/queryKeys";
import { useTypewriter } from "@/lib/motion";
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
      <ChatPane
        key={activeId}
        threadId={activeId}
        title={threadList?.find((t) => t.id === activeId)?.title ?? null}
        onNew={newChat}
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
  title,
  onNew,
}: {
  threadId: string;
  title: string | null;
  onNew: () => void;
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
      title={title}
      onNew={onNew}
    />
  );
}

function ChatConversation({
  threadId,
  initialMessages,
  title,
  onNew,
}: {
  threadId: string;
  initialMessages: UIMessage[];
  title: string | null;
  onNew: () => void;
}) {
  const qc = useQueryClient();
  const setChatDraft = useUi((s) => s.setChatDraft);
  const clearChatDraft = useUi((s) => s.clearChatDraft);
  const [params, setParams] = useSearchParams();
  // Seed the composer from any saved draft for this thread (the pane remounts on
  // thread switch, so local state alone would drop unsent input). Read once at
  // mount via getState to avoid subscribing the whole pane to the draft map.
  const [input, setInput] = useState(() => useUi.getState().chatDrafts[threadId] ?? "");
  // The home composer can hand over a library scope with its first question.
  const location = useLocation();
  const [filters, setFilters] = useState<ChatFilters>(
    () => (location.state as { filters?: ChatFilters } | null)?.filters ?? {},
  );
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
  // History loaded with the thread doesn't animate; turns sent now do.
  const [loadedIds] = useState(() => new Set(initialMessages.map((m) => m.id)));
  // The server names a new thread after its first turn — the title types in.
  const typed = useTypewriter(title);

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
  // Did any of the last answer stream in before an error cut it off?
  const lastMsg = messages[messages.length - 1];
  const partialAnswer =
    lastMsg?.role === "assistant" &&
    (lastMsg.parts ?? []).some((p) => p.type === "text" && !!(p as { text?: string }).text);
  // Any answer with sources widens the column for the sources column (≥1600px).
  const hasSide = messages.some((m) =>
    (m.parts ?? []).some((p) => (p as { type: string }).type === CITATIONS_PART),
  );

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Header: the thread's title and its actions. Navigation is the rail
          (tabs on phones) and the thread list is the context panel. */}
      <div className="flex h-14 shrink-0 items-center gap-2 pl-4 pr-2 md:pl-4 md:pr-3">
        <h1 className="min-w-0 flex-1 truncate font-display text-[15px] font-semibold leading-5 tracking-[-0.01em]">
          {isIdle ? (
            "New chat"
          ) : (
            <span className={cn(typed.typing && "m-typing")}>{typed.shown || "Conversation"}</span>
          )}
        </h1>
        {!isIdle && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Conversation actions">
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
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onNew}
          aria-label="New chat"
          title="New chat (⌘⇧O)"
        >
          <Plus className="size-[18px]" />
        </Button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-2 md:px-6">
        <div
          className={cn(
            "chat-col",
            hasSide && "has-side",
            isIdle ? "flex min-h-full flex-col justify-center" : "space-y-[26px]",
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
                fresh={!loadedIds.has(m.id)}
                // The turn that broke keeps its partial text, marked where it stopped.
                interrupted={!!error && !isStreaming && i === messages.length - 1}
              />
            ))
          )}
          {error && !isStreaming && (
            <ChatError
              error={error}
              onRetry={() => regenerate(normalizeFilters(filters))}
              partial={partialAnswer}
            />
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer dock */}
      <div className="relative shrink-0 bg-linear-to-t from-bg from-70% to-transparent px-3 pb-3 md:px-6 md:pb-[18px]">
        <div className={cn("chat-col", hasSide && "has-side")}>
          <div className="chat-dock-inner relative">
            {/* Jump-to-latest — only while reading above the fold mid-conversation. */}
            {!pinned && !isIdle && (
              <button
                onClick={scrollToBottom}
                aria-label="Jump to latest"
                className="absolute -top-12 left-1/2 z-10 flex size-9 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-surface-2 text-fg-muted shadow-lg shadow-black/30 transition-colors hover:text-fg"
              >
                <ArrowDown className="size-4" />
              </button>
            )}
            <Composer
              ref={composerRef}
              value={input}
              onChange={onInputChange}
              onSubmit={submit}
              onStop={stop}
              streaming={isStreaming}
              placeholder={isIdle ? "Ask your library…" : "Reply to Merlin…"}
              filters={filters}
              setFilters={setFilters}
              meter={!isIdle ? <ContextMeter usage={latestUsage(messages)} /> : undefined}
            />
            <p className="mt-2 hidden text-center font-mono text-[11px] leading-4 text-fg-subtle md:block">
              Merlin can be wrong. Library answers cite their sources.
            </p>
          </div>
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
/** A failed/interrupted turn (mockup `#chat-error`): what happened, the
 * partial answer kept above it, Retry and the details to copy. A step-limit
 * stop (the agent searching without settling — `chat_max_requests`) gets its
 * own advice, since that one is usually the library not covering the
 * question. "Switch model" arrives with the model menu (Phase 1). */
function ChatError({
  error,
  onRetry,
  partial,
}: {
  error: Error;
  onRetry: () => void;
  /** Some of the answer streamed before it broke (it stays above). */
  partial: boolean;
}) {
  const msg = errorText(error?.message ?? "");
  const isLimit = /request[_ ]?limit|usage limit|exceeded|step/i.test(msg);
  const at = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="rounded-[14px] border border-fail/40 bg-fail/[0.06] px-4 py-3.5 shadow-[inset_3px_0_0_var(--color-fail)] md:ml-11">
      <div className="flex flex-wrap items-center gap-2.5">
        <span className="inline-flex items-center gap-1 rounded-[5px] border border-fail/60 px-1.5 py-0.5 font-mono text-[10.5px] font-medium tracking-[0.08em] text-fail">
          <AlertTriangle className="size-3" /> ERROR
        </span>
        <p className="text-[15px] font-medium text-fg">
          {isLimit ? "Merlin reached its step limit for this answer" : "The answer was interrupted"}
        </p>
      </div>
      <p className="mt-2 text-[14px] leading-[21px] text-fg-muted">
        {isLimit
          ? "It searched several times without settling — often a sign your library doesn't cover this. Try rephrasing, or narrow the Library scope (or raise CHAT_MAX_REQUESTS)."
          : partial
            ? "The partial answer above is kept. Retry asks again from your question."
            : "Nothing came back this time. Retry asks again from your question."}
      </p>
      {msg && !isLimit && (
        <p className="mt-1.5 break-words font-mono text-[11px] leading-4 text-fg-subtle">
          {msg} · {at}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={onRetry}>
          <RotateCw className="size-3.5" /> Retry
        </Button>
        {msg && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard?.writeText(`${msg} (${at})`);
              toast("Error details copied");
            }}
          >
            Copy details
          </Button>
        )}
      </div>
    </div>
  );
}

/** The SDK hands over the response body as the message; ours is the API's
 *  `{error:{code,message}}` envelope — show its message, not the JSON. */
function errorText(raw: string): string {
  try {
    const body = JSON.parse(raw) as { error?: { message?: string; code?: string } };
    if (body?.error?.message) return body.error.code ? `${body.error.message} (${body.error.code})` : body.error.message;
  } catch {
    /* not JSON — plain text */
  }
  return raw;
}

function IdleState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center gap-5 py-12 text-center">
      <Mark size={40} decorative />
      <div className="space-y-1.5">
        <p className="font-display text-[26px] font-semibold leading-tight tracking-[-0.02em]">
          What do you want to know?
        </p>
        <p className="text-[15px] text-fg-muted">
          Merlin answers from everything you've saved, with sources.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {STARTERS.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="inline-flex min-h-9 items-center gap-2 rounded-full border border-border px-3.5 py-1.5 text-left text-[14px] leading-5 text-fg-muted transition-colors hover:border-border-strong hover:bg-surface hover:text-fg"
          >
            <Sparkles className="size-3.5 shrink-0 text-ui-icon" />
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
