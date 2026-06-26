import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, ArrowDown, Square, Sparkles } from "lucide-react";
import { useAgentChat, latestUsage, type ChatFilters } from "@/hooks/useAgentChat";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import { Button } from "@/components/ui/button";
import { Message } from "@/components/chat/Message";
import { ContextMeter } from "@/components/chat/UsageFooter";
import { AutoGrowTextarea } from "@/components/common/AutoGrowTextarea";
import { cn } from "@/lib/utils";

const STARTERS = [
  "What's the main argument?",
  "Give me the key takeaways",
  "Explain this like I'm new to the topic",
  "What's the most surprising claim here?",
];

/**
 * Chat scoped to a single item, using its full transcript (no RAG). Ephemeral:
 * mount with `key={item.id}` in the Reader so navigating items resets it.
 */
export function ItemChat({
  itemId,
  className,
}: {
  itemId: string;
  className?: string;
}) {
  // A stable per-item `id` is required: the AI SDK `useChat` (driven through the
  // shared module-level transport) only reflects streamed parts back into
  // `messages` when its Chat instance is keyed by an id. Without it the answer
  // streams from the server but never renders. Keyed to the item; the Reader
  // remounts via `key={item.id}`, so the thread stays ephemeral per item.
  const { messages, isStreaming, send, regenerate, editAndResend, stop } = useAgentChat({
    id: `item-${itemId}`,
  });
  const [input, setInput] = useState("");
  const { scrollRef, bottomRef, pinned, scrollToBottom } = useStickToBottom(messages);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  const filters = useMemo<ChatFilters>(() => ({ item_id: itemId }), [itemId]);

  const runSend = useCallback(
    (q: string) => {
      send(q, filters);
      scrollToBottom();
    },
    [send, filters, scrollToBottom],
  );

  // Stable per-message handlers so the memoized <Message> rows don't re-render on
  // every streamed token.
  const handleRegenerate = useCallback(() => {
    regenerate(filters);
    scrollToBottom();
  }, [regenerate, filters, scrollToBottom]);
  const handleEdit = useCallback(
    (id: string, text: string) => {
      editAndResend(id, text, filters);
      scrollToBottom();
    },
    [editAndResend, filters, scrollToBottom],
  );

  // Focus the composer when the per-item chat mounts (Reader remounts per item).
  useEffect(() => {
    composerRef.current?.focus();
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
    <div
      className={cn(
        "flex h-[clamp(420px,60vh,720px)] flex-col rounded-[10px] border border-border bg-surface",
        className,
      )}
    >
      {/* Thread */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-4">
        {isIdle ? (
          <div className="flex h-full flex-col items-center justify-center gap-5 text-center">
            <div className="flex size-11 items-center justify-center rounded-full bg-accent-subtle text-accent">
              <Sparkles className="size-5" strokeWidth={1.5} />
            </div>
            <div className="space-y-1">
              <p className="text-[15px] font-semibold">Chat with this item</p>
              <p className="text-[13px] text-fg-muted">
                Answers come from the full transcript of this item.
              </p>
            </div>
            <div className="flex w-full max-w-sm flex-col gap-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => runSend(s)}
                  className="group flex items-center gap-2.5 rounded-[10px] border border-border bg-surface-2 px-3.5 py-2.5 text-left text-[13px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
                >
                  <Sparkles className="size-3.5 shrink-0 text-fg-subtle group-hover:text-accent" />
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((m, i) => (
              <Message
                key={m.id}
                message={m}
                isLast={i === messages.length - 1}
                isStreaming={isStreaming}
                onRegenerate={handleRegenerate}
                onFollowup={runSend}
                onEdit={handleEdit}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="relative border-t border-border p-3">
        {!isIdle && !pinned && (
          <button
            onClick={scrollToBottom}
            aria-label="Jump to latest"
            className="absolute -top-5 left-1/2 z-10 flex size-8 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-surface-2 text-fg-muted shadow-lg shadow-black/30 transition-colors hover:text-fg"
          >
            <ArrowDown className="size-4" />
          </button>
        )}
        {!isIdle && (
          <div className="mb-1.5 flex justify-end px-1">
            <ContextMeter usage={latestUsage(messages)} />
          </div>
        )}
        <div className="flex items-end gap-2">
          <AutoGrowTextarea
            ref={composerRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask about this item…"
            className="max-h-32 min-h-[40px] flex-1 rounded-[10px] border border-border bg-surface-2 px-3.5 py-2.5 text-[16px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-border-strong sm:text-[14px]"
          />
          {isStreaming ? (
            <Button onClick={stop} variant="secondary" size="icon" className="size-10 rounded-[10px]">
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              onClick={submit}
              disabled={!input.trim()}
              size="icon"
              className="size-10 rounded-[10px]"
            >
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
