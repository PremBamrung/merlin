import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Sparkles,
  ArrowUp,
  Square,
  SlidersHorizontal,
  MessageSquare,
  Plus,
  X,
} from "lucide-react";
import { useChatStream } from "@/hooks/useChatStream";
import { useTags, useSourceTypes } from "@/hooks/useMeta";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Message } from "@/components/chat/Message";
import type { ChatFilters } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

const STARTERS = [
  "What are the recurring themes across my library?",
  "Summarize what I've saved about AI agents.",
  "Which videos discuss business strategy?",
];

export default function ChatRoute() {
  const { messages, isStreaming, send, regenerate, stop, reset } = useChatStream();
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState("");
  const [filters, setFilters] = useState<ChatFilters>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const sentPrefill = useRef(false);

  const filtersActive =
    (filters.source_types?.length ?? 0) + (filters.tags?.length ?? 0);

  // Prefill from ?q= (Today omnibox / command palette) — auto-send once.
  useEffect(() => {
    const q = params.get("q");
    if (q && !sentPrefill.current) {
      sentPrefill.current = true;
      send(q, filters);
      params.delete("q");
      setParams(params, { replace: true });
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
    <div className="flex h-[calc(100vh-3.5rem-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4">
        <h1 className="text-[24px] font-semibold">Chat</h1>
        <div className="flex items-center gap-2">
          {!isIdle && (
            <Button variant="ghost" size="sm" onClick={reset} disabled={isStreaming}>
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
                turn={m}
                isLast={i === messages.length - 1}
                isStreaming={isStreaming}
                onRegenerate={regenerate}
                onFollowup={(q) => send(q, normalizeFilters(filters))}
              />
            ))
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

function normalizeFilters(f: ChatFilters): ChatFilters {
  return {
    source_types: f.source_types?.length ? f.source_types : null,
    tags: f.tags?.length ? f.tags : null,
  };
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
