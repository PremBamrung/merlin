import { useMemo, useState } from "react";
import { ArrowUp, Square, Sparkles } from "lucide-react";
import { useAgentChat, type ChatFilters } from "@/hooks/useAgentChat";
import { useStickToBottom } from "@/hooks/useStickToBottom";
import { Button } from "@/components/ui/button";
import { Message } from "@/components/chat/Message";
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
  const { messages, isStreaming, send, regenerate, stop } = useAgentChat();
  const [input, setInput] = useState("");
  const { scrollRef, bottomRef } = useStickToBottom(messages);

  const filters = useMemo<ChatFilters>(() => ({ item_id: itemId }), [itemId]);

  const submit = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    send(q, filters);
    setInput("");
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
                  onClick={() => send(s, filters)}
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
                onRegenerate={() => regenerate(filters)}
                onFollowup={(q) => send(q, filters)}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
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
            placeholder="Ask about this item…"
            className="max-h-32 min-h-[40px] flex-1 resize-none rounded-[10px] border border-border bg-surface-2 px-3.5 py-2.5 text-[16px] text-fg outline-none transition-colors placeholder:text-fg-subtle focus:border-border-strong sm:text-[14px]"
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
