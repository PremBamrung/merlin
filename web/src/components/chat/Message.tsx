import { RotateCw } from "lucide-react";
import type { ChatTurn } from "@/hooks/useChatStream";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/common/Markdown";
import { CopyButton } from "@/components/common/CopyButton";
import { CitationCard } from "@/components/chat/CitationCard";

const FOLLOWUPS = [
  "Why?",
  "Counterpoints?",
  "Give me an example",
  "Summarize key points",
];

/**
 * One chat turn (user bubble or assistant answer + citations + actions).
 * Shared by the global Chat page and the per-item Reader chat tab.
 */
export function Message({
  turn,
  isLast,
  isStreaming,
  onRegenerate,
  onFollowup,
}: {
  turn: ChatTurn;
  isLast: boolean;
  isStreaming: boolean;
  onRegenerate: () => void;
  onFollowup: (q: string) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-[14px] rounded-tr-sm bg-surface-2 px-4 py-2.5 text-[14px] text-fg">
          {turn.content}
        </div>
      </div>
    );
  }

  const showActions = isLast && !turn.streaming && !turn.error;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-accent">✦</span>
        <span className="eyebrow">Merlin</span>
      </div>

      {turn.error ? (
        <div className="rounded-[10px] border border-accent-border bg-accent-subtle/40 px-4 py-3 text-[13px] text-accent">
          {turn.error}
          {isLast && (
            <button onClick={onRegenerate} className="ml-2 underline hover:text-accent-hover">
              Try again
            </button>
          )}
        </div>
      ) : (
        <div className="max-w-none">
          {turn.content ? (
            <Markdown>{turn.content}</Markdown>
          ) : (
            <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-fg-muted align-middle" />
          )}
          {turn.streaming && turn.content && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-accent align-middle" />
          )}
        </div>
      )}

      {/* Citations */}
      {turn.citations && turn.citations.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="eyebrow">Sources</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {turn.citations.map((c, i) => (
              <CitationCard key={`${c.item_id}-${i}`} citation={c} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Regenerate + follow-ups */}
      {showActions && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button variant="ghost" size="sm" onClick={onRegenerate} disabled={isStreaming}>
            <RotateCw className="size-3.5" /> Regenerate
          </Button>
          <CopyButton text={turn.content} label="Copy" />
          <span className="text-border-strong">·</span>
          {FOLLOWUPS.map((f) => (
            <button
              key={f}
              onClick={() => onFollowup(f)}
              disabled={isStreaming}
              className="rounded-full border border-border px-2.5 py-1 text-[12px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg disabled:opacity-50"
            >
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
