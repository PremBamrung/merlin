import { useEffect, useRef, useState } from "react";
import {
  RotateCw,
  Wrench,
  Search,
  FileText,
  List,
  Tags,
  Layers,
  ChevronRight,
  Brain,
  Loader2,
  Sparkles,
} from "lucide-react";
import type { UIMessage } from "ai";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/common/Markdown";
import { CopyButton } from "@/components/common/CopyButton";
import { CitationCard } from "@/components/chat/CitationCard";
import {
  CITATIONS_PART,
  SOURCES_VIEWED_PART,
  WORK_TIMING_PART,
  MESSAGE_TIME_PART,
  linkifyCitationMarkers,
  stripCitationMarkers,
  type Citation,
} from "@/hooks/useAgentChat";
import { msgTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const FOLLOWUPS = ["Why?", "Counterpoints?", "Give me an example", "Summarize key points"];

const TOOL_ICONS: Record<string, typeof Wrench> = {
  search_library: Search,
  get_item: FileText,
  browse_library: List,
  list_tags: Tags,
  list_source_types: Layers,
};

// Loose view of a UIMessage part — the SDK's union is wide; we narrow on `type`.
type AnyPart = {
  type: string;
  text?: string;
  toolName?: string;
  state?: string;
  input?: unknown;
  output?: unknown;
  errorText?: string;
  data?: { items?: Citation[]; seconds?: number; ms?: number };
};

function isToolPart(p: AnyPart): boolean {
  return p.type === "dynamic-tool" || p.type.startsWith("tool-");
}

function toolName(p: AnyPart): string {
  return p.toolName ?? (p.type.startsWith("tool-") ? p.type.slice(5) : "tool");
}

/**
 * Segments of an assistant turn: spoken text vs. "work" (a run of consecutive
 * reasoning + tool-call parts). Work runs collapse into a single `WorkTrace`
 * disclosure; text between runs renders inline. Empty reasoning parts are
 * dropped so a stray placeholder never opens a work block on its own.
 */
type Segment =
  | { kind: "text"; text: string; key: number }
  | { kind: "work"; parts: AnyPart[]; key: number };

function groupParts(parts: AnyPart[]): Segment[] {
  const segments: Segment[] = [];
  let work: AnyPart[] | null = null;
  parts.forEach((p, i) => {
    const isWork = isToolPart(p) || p.type === "reasoning";
    if (isWork) {
      if (p.type === "reasoning" && !p.text) return;
      if (!work) {
        work = [];
        segments.push({ kind: "work", parts: work, key: i });
      }
      work.push(p);
    } else if (p.type === "text" && p.text) {
      work = null;
      segments.push({ kind: "text", text: p.text, key: i });
    }
  });
  return segments;
}

/**
 * One chat turn rendered from the Vercel AI SDK message-parts protocol: a user
 * bubble, or an assistant answer interleaving reasoning, tool calls (with args +
 * results), and text — plus a consolidated Sources list. Shared by the global
 * Chat page and the Reader's per-item chat.
 */
export function Message({
  message,
  isLast,
  isStreaming,
  onRegenerate,
  onFollowup,
}: {
  message: UIMessage;
  isLast: boolean;
  isStreaming: boolean;
  onRegenerate: () => void;
  onFollowup: (q: string) => void;
}) {
  const parts = (message.parts ?? []) as AnyPart[];
  // Stripped of inline `[#id]` markers — used for the copy action.
  const textContent = stripCitationMarkers(
    parts
      .filter((p) => p.type === "text")
      .map((p) => p.text ?? "")
      .join(""),
  );

  // Wall-clock time the message was created (epoch ms), persisted as a data-part
  // at end-of-turn; absent on old threads, in which case we render no time.
  const timeMs = parts.find((p) => p.type === MESSAGE_TIME_PART)?.data?.ms ?? null;
  const timeLabel = timeMs != null ? msgTime(timeMs) : "";

  if (message.role === "user") {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[14px] rounded-tr-sm bg-surface-2 px-4 py-2.5 text-[14px] text-fg">
          {textContent}
        </div>
        {timeLabel && (
          <span className="px-1 text-[11px] text-fg-subtle">{timeLabel}</span>
        )}
      </div>
    );
  }

  // Two citation tiers arrive at end-of-turn: items the answer used (Sources)
  // and items a tool surfaced but the answer didn't cite (Also searched).
  const citations: Citation[] = parts
    .filter((p) => p.type === CITATIONS_PART)
    .flatMap((p) => p.data?.items ?? []);
  const alsoViewed: Citation[] = parts
    .filter((p) => p.type === SOURCES_VIEWED_PART)
    .flatMap((p) => p.data?.items ?? []);

  const isThisStreaming = isStreaming && isLast;
  const hasVisible = parts.some(
    (p) => (p.type === "text" && p.text) || p.type === "reasoning" || isToolPart(p),
  );
  const showActions = isLast && !isThisStreaming && !!textContent;
  const segments = groupParts(parts);
  // Persisted work-phase duration (set on finish; present after a reload). Shown
  // on the first work block when its live timer isn't available.
  const persistedSeconds =
    parts.find((p) => p.type === WORK_TIMING_PART)?.data?.seconds ?? null;
  const firstWorkIdx = segments.findIndex((s) => s.kind === "work");

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-accent">✦</span>
        <span className="eyebrow">Merlin</span>
        {timeLabel && (
          <span className="ml-auto text-[11px] text-fg-subtle">{timeLabel}</span>
        )}
      </div>

      <div className="space-y-2.5">
        {segments.map((seg, idx) => {
          const isLastSeg = idx === segments.length - 1;
          if (seg.kind === "work") {
            return (
              <WorkTrace
                key={seg.key}
                parts={seg.parts}
                streaming={isThisStreaming && isLastSeg}
                fallbackSeconds={idx === firstWorkIdx ? persistedSeconds : null}
              />
            );
          }
          return (
            <div key={seg.key} className="max-w-none">
              <Markdown>{linkifyCitationMarkers(seg.text, citations)}</Markdown>
            </div>
          );
        })}

        {/* Thinking placeholder before any content streams in. */}
        {isThisStreaming && !hasVisible && (
          <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-fg-muted align-middle" />
        )}
      </div>

      {citations.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="eyebrow">Sources</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {citations.map((c, i) => (
              <CitationCard key={`${c.item_id}-${i}`} citation={c} index={i} />
            ))}
          </div>
        </div>
      )}

      {alsoViewed.length > 0 && <AlsoSearched items={alsoViewed} />}

      {showActions && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button variant="ghost" size="sm" onClick={onRegenerate} disabled={isStreaming}>
            <RotateCw className="size-3.5" /> Regenerate
          </Button>
          <CopyButton text={textContent} label="Copy" />
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

/**
 * A run of reasoning + tool calls collapsed into one disclosure. The header is a
 * single live summary ("Searching your library… 3s" while working, then
 * "Searched & reasoned · 6 steps · 5s"); expanding reveals each reasoning text
 * and tool call (each tool keeps its own result expansion). Auto-expands while
 * the turn streams so steps appear live, then auto-collapses when it settles —
 * still user-toggleable afterwards.
 */
function WorkTrace({
  parts,
  streaming,
  fallbackSeconds,
}: {
  parts: AnyPart[];
  streaming: boolean;
  fallbackSeconds: number | null;
}) {
  // Auto-expand while streaming, auto-collapse when it settles — but stay
  // user-toggleable. This is the documented "adjust state on prop change"
  // pattern: flip `open` to match `streaming` only on the transition, so a
  // manual toggle between transitions sticks.
  const [open, setOpen] = useState(streaming);
  const [prevStreaming, setPrevStreaming] = useState(streaming);
  if (streaming !== prevStreaming) {
    setPrevStreaming(streaming);
    setOpen(streaming);
  }

  // Elapsed seconds — only meaningful for turns generated live this session.
  // Reloaded threads never stream, so `elapsed` stays null and we omit it.
  const startRef = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  useEffect(() => {
    if (!streaming) return;
    if (startRef.current == null) startRef.current = Date.now();
    const tick = () => setElapsed(Math.round((Date.now() - startRef.current!) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [streaming]);

  const toolParts = parts.filter(isToolPart);
  // Live timer wins; fall back to the persisted duration on a reloaded thread.
  const seconds = elapsed != null ? elapsed : fallbackSeconds;
  const summary = workSummary(streaming, toolParts, seconds);

  return (
    <div className="rounded-[10px] border border-border bg-surface-2/50 text-[12.5px]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        {streaming ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-fg-subtle" />
        ) : (
          <Sparkles className="size-3.5 shrink-0 text-fg-subtle" />
        )}
        <span className="font-medium text-fg-muted">{summary}</span>
        <ChevronRight
          className={cn("ml-auto size-3.5 shrink-0 transition-transform", open && "rotate-90")}
        />
      </button>
      {open && (
        <div className="space-y-2 border-t border-border px-3 py-2.5">
          {parts.map((p, i) => {
            if (p.type === "reasoning" && p.text) return <ReasoningInline key={i} text={p.text} />;
            if (isToolPart(p)) return <ToolTrace key={i} part={p} />;
            return null;
          })}
        </div>
      )}
    </div>
  );
}

/** Collapsed-header label for a `WorkTrace`. */
function workSummary(
  streaming: boolean,
  toolParts: AnyPart[],
  elapsed: number | null,
): string {
  const secs = elapsed != null ? `${elapsed}s` : null;
  if (streaming) {
    const active =
      [...toolParts]
        .reverse()
        .find((p) => p.state !== "output-available" && p.state !== "output-error") ??
      toolParts[toolParts.length - 1];
    const verb = active ? streamingVerb(toolName(active)) : "Thinking";
    return secs ? `${verb}… ${secs}` : `${verb}…`;
  }
  const steps = toolParts.length;
  const bits = [steps > 0 ? "Searched & reasoned" : "Thought"];
  if (steps > 0) bits.push(`${steps} step${steps === 1 ? "" : "s"}`);
  if (secs) bits.push(secs);
  return bits.join(" · ");
}

function streamingVerb(name: string): string {
  switch (name) {
    case "search_library":
      return "Searching your library";
    case "get_item":
      return "Reading sources";
    case "browse_library":
    case "list_tags":
    case "list_source_types":
      return "Browsing your library";
    default:
      return "Working";
  }
}

/** One reasoning step shown inside an expanded `WorkTrace`. */
function ReasoningInline({ text }: { text: string }) {
  return (
    <div className="flex gap-2 text-[12.5px] italic leading-relaxed text-fg-muted">
      <Brain className="mt-0.5 size-3.5 shrink-0 text-fg-subtle" />
      <span className="whitespace-pre-wrap">{text}</span>
    </div>
  );
}

/** Items a tool surfaced but the answer didn't cite — a collapsed disclosure
 * below the primary Sources grid. */
function AlsoSearched({ items }: { items: Citation[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-[10px] border border-border bg-surface-2/50">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[12px] text-fg-muted"
      >
        <Search className="size-3.5 text-fg-subtle" />
        <span className="eyebrow">Also searched ({items.length})</span>
        <ChevronRight
          className={cn("ml-auto size-3.5 transition-transform", open && "rotate-90")}
        />
      </button>
      {open && (
        <div className="grid grid-cols-1 gap-2 border-t border-border px-3 py-2.5 sm:grid-cols-2">
          {items.map((c, i) => (
            <CitationCard key={`${c.item_id}-${i}`} citation={c} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}

/** One tool call: name + args, with a collapsible result. This is the primary
 * "show what Merlin actually did" surface. */
function ToolTrace({ part }: { part: AnyPart }) {
  const [open, setOpen] = useState(false);
  const name = toolName(part);
  const Icon = TOOL_ICONS[name] ?? Wrench;
  const args = part.input as Record<string, unknown> | undefined;
  const done = part.state === "output-available" || part.state === "output-error";
  const failed = part.state === "output-error";
  const output =
    typeof part.output === "string" ? part.output : part.output ? JSON.stringify(part.output, null, 2) : "";

  const argSummary =
    args && Object.keys(args).length > 0
      ? Object.entries(args)
          .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
          .join(", ")
      : null;

  return (
    <div className="rounded-[10px] border border-border bg-surface-2/50 text-[12.5px]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        disabled={!done}
      >
        <Icon className={cn("size-3.5", failed ? "text-accent" : "text-fg-subtle")} />
        <span className="font-mono text-fg-muted">{name}</span>
        {argSummary && (
          <span className="min-w-0 flex-1 truncate font-mono text-fg-subtle">({argSummary})</span>
        )}
        {!done ? (
          <span className="ml-auto flex items-center gap-1 text-fg-subtle">
            <span className="size-1.5 animate-pulse rounded-full bg-accent" /> running
          </span>
        ) : (
          <ChevronRight
            className={cn("ml-auto size-3.5 shrink-0 transition-transform", open && "rotate-90")}
          />
        )}
      </button>
      {open && done && output && (
        <pre className="overflow-x-auto whitespace-pre-wrap border-t border-border px-3 py-2 font-mono text-[11.5px] leading-relaxed text-fg-muted">
          {failed ? part.errorText || output : output}
        </pre>
      )}
    </div>
  );
}
