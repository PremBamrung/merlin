import { type TurnUsage } from "@/hooks/useAgentChat";
import { compactNumber, thousands } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Context-fill percentage (0–100), or null when the limit is unknown. */
function fillPct(usage: TurnUsage): number | null {
  if (!usage.context_used || !usage.context_limit) return null;
  return Math.min(100, (usage.context_used / usage.context_limit) * 100);
}

/** Tone by how full the window is — amber past 75%, red past 90%. */
function tone(pct: number | null): { text: string; bar: string } {
  if (pct == null) return { text: "text-fg-subtle", bar: "bg-fg-subtle/60" };
  if (pct > 90) return { text: "text-red-500", bar: "bg-red-500" };
  if (pct > 75) return { text: "text-amber-500", bar: "bg-amber-500" };
  return { text: "text-fg-subtle", bar: "bg-fg-subtle/60" };
}

/** Sub-cent costs need precision; show 4 decimals under a cent, else 2. */
function formatCost(usd: number | null, estimated: boolean): string | null {
  if (usd == null) return null;
  const s = usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
  return estimated ? `~${s}` : s;
}

/**
 * Compact footer under an assistant answer: tokens in/out, estimated cost, and
 * context-window occupancy with a thin fill bar. Hidden until the turn finishes
 * (the data-part arrives at end-of-turn). The `title` spells out the exact
 * figures on hover.
 */
export function UsageFooter({ usage }: { usage: TurnUsage }) {
  const pct = fillPct(usage);
  const t = tone(pct);
  const cost = formatCost(usage.cost_usd, usage.cost_estimated);

  const detail = [
    usage.input_tokens != null && `Input: ${thousands(usage.input_tokens)} tokens`,
    usage.cache_read_tokens
      ? `  (${thousands(usage.cache_read_tokens)} cached)`
      : "",
    usage.output_tokens != null && `\nOutput: ${thousands(usage.output_tokens)} tokens`,
    usage.requests && usage.requests > 1 && `\nRequests: ${usage.requests}`,
    usage.context_used != null &&
      usage.context_limit != null &&
      `\nContext: ${thousands(usage.context_used)} / ${thousands(usage.context_limit)}`,
    cost && `\nEstimated cost: ${cost}`,
  ]
    .filter(Boolean)
    .join("");

  return (
    <div
      className="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 pt-0.5 text-[11px] text-fg-subtle"
      title={detail}
    >
      <span className="tabular-nums">
        ↑{compactNumber(usage.input_tokens)} ↓{compactNumber(usage.output_tokens)}
      </span>
      {cost && (
        <>
          <span className="text-fg-subtle/50">·</span>
          <span className="tabular-nums">{cost}</span>
        </>
      )}
      {usage.context_used != null && (
        <>
          <span className="text-fg-subtle/50">·</span>
          <span className={cn("flex items-center gap-1.5 tabular-nums", t.text)}>
            ctx {compactNumber(usage.context_used)}
            {usage.context_limit != null && (
              <>
                /{compactNumber(usage.context_limit)}
                {pct != null && (
                  <span className="inline-flex h-1 w-10 overflow-hidden rounded-full bg-border align-middle">
                    <span
                      className={cn("h-full rounded-full", t.bar)}
                      style={{ width: `${Math.max(2, pct)}%` }}
                    />
                  </span>
                )}
                {pct != null && <span>{pct < 1 ? "<1" : Math.round(pct)}%</span>}
              </>
            )}
          </span>
        </>
      )}
    </div>
  );
}

/**
 * A running context-window meter for the composer, fed by the latest turn's
 * usage. Surfaces when a long thread is filling the window so you know to start
 * a fresh conversation. Hidden until the first turn finishes or when the limit
 * is unknown.
 */
export function ContextMeter({
  usage,
  className,
}: {
  usage: TurnUsage | null;
  className?: string;
}) {
  if (!usage || !usage.context_used || !usage.context_limit) return null;
  const pct = fillPct(usage);
  const t = tone(pct);
  return (
    <div
      className={cn("flex items-center gap-1.5 text-[11px] tabular-nums", t.text, className)}
      title={`Conversation is using ${thousands(usage.context_used)} of the model's ${thousands(
        usage.context_limit,
      )}-token context window.${pct != null && pct > 75 ? " Consider starting a new conversation." : ""}`}
    >
      <span className="inline-flex h-1 w-12 overflow-hidden rounded-full bg-border">
        <span
          className={cn("h-full rounded-full", t.bar)}
          style={{ width: `${pct != null ? Math.max(2, pct) : 0}%` }}
        />
      </span>
      <span>
        {compactNumber(usage.context_used)} / {compactNumber(usage.context_limit)}
        {pct != null && ` · ${pct < 1 ? "<1" : Math.round(pct)}%`}
      </span>
    </div>
  );
}
