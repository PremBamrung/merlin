import { memo, useEffect, useRef, useState } from "react";
import {
  RotateCw,
  Wrench,
  Search,
  FileText,
  List,
  Tags,
  Layers,
  Globe,
  ChevronDown,
  ChevronRight,
  Brain,
  Loader2,
  Check,
  Pencil,
} from "lucide-react";
import type { UIMessage } from "ai";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/common/Markdown";
import { CopyButton } from "@/components/common/CopyButton";
import { AutoGrowTextarea } from "@/components/common/AutoGrowTextarea";
import { SourceCard } from "@/components/chat/SourceCard";
import { Mark } from "@/components/brand/Mark";
import { UsageFooter } from "@/components/chat/UsageFooter";
import {
  CITATIONS_PART,
  SOURCES_VIEWED_PART,
  WORK_TIMING_PART,
  MESSAGE_TIME_PART,
  linkifyCitationMarkers,
  messageUsage,
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
  web_search: Globe,
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
 * One chat turn rendered from the Vercel AI SDK message-parts protocol, laid
 * out Claude-like (docs/EVERYDAY_AI_PLAN.md § Messages): a user bubble on the
 * right; an assistant answer as full-width prose beside the hat, with its agent
 * work folded into one summary line, numbered citation chips, source cards and
 * the turn's usage. Shared by the Chat page and the Reader's item chat
 * (`compact`: no avatar gutter — that column is narrow).
 *
 * On the Chat page the sources sit in `.ai-side`, which index.css turns into a
 * sticky column beside the answer from 1600px.
 *
 * Memoized: while a turn streams, the AI SDK mutates only the last message and
 * keeps completed message objects referentially stable, so a `memo` here skips
 * re-rendering (and re-parsing the markdown of) every finished turn on each
 * token. Relies on the caller passing stable callback props (see chat.tsx).
 */
export const Message = memo(function Message({
  message,
  isLast,
  isStreaming,
  onRegenerate,
  onFollowup,
  onEdit,
  compact = false,
  fresh = false,
  interrupted = false,
}: {
  message: UIMessage;
  isLast: boolean;
  isStreaming: boolean;
  onRegenerate: () => void;
  onFollowup: (q: string) => void;
  /** Edit a user turn and re-run from there. Omit to disable editing. */
  onEdit?: (id: string, text: string) => void;
  compact?: boolean;
  /** Sent in this session (not loaded from history) — rises into the thread. */
  fresh?: boolean;
  /** The stream failed on this turn: show where the answer stopped. */
  interrupted?: boolean;
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
      <UserMessage
        text={textContent}
        fresh={fresh}
        timeLabel={timeLabel}
        disabled={isStreaming}
        onEdit={onEdit ? (text) => onEdit(message.id, text) : undefined}
      />
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
  // Per-turn tokens / est. cost / context occupancy (lands at end-of-turn).
  const usage = messageUsage(message);

  const isThisStreaming = isStreaming && isLast;
  const hasVisible = parts.some(
    (p) => (p.type === "text" && p.text) || p.type === "reasoning" || isToolPart(p),
  );
  const showFollowups = isLast && !isThisStreaming && !!textContent;
  const segments = groupParts(parts);
  // Persisted work-phase duration (set on finish; present after a reload). Shown
  // on the first work block when its live timer isn't available.
  const persistedSeconds =
    parts.find((p) => p.type === WORK_TIMING_PART)?.data?.seconds ?? null;
  const firstWorkIdx = segments.findIndex((s) => s.kind === "work");
  const showCopy = !isThisStreaming && !!textContent;
  const hasSide = citations.length > 0 || alsoViewed.length > 0 || !!usage;

  return (
    <div
      className={cn("msg-ai group/msg", compact && "compact", citations.length > 0 && "with-side")}
    >
      {!compact && (
        <div className="ai-av" title={timeLabel || undefined}>
          <Mark size={22} decorative />
        </div>
      )}

      <div className="min-w-0">
        {segments.map((seg, idx) => {
          const isLastSeg = idx === segments.length - 1;
          const writing = isThisStreaming && isLastSeg;
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
            // Joy — writing: a glowing caret rides the end of the answer.
            <Markdown
              key={seg.key}
              className={cn("[&>:first-child]:mt-0 [&>:last-child]:mb-0", writing && "m-streaming")}
            >
              {linkifyCitationMarkers(seg.text, citations, message.id)}
            </Markdown>
          );
        })}

        {interrupted && textContent && (
          <span className="mt-1 inline-block rounded border border-dashed border-border-strong px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-fg-subtle">
            Stopped here
          </span>
        )}

        {/* Joy — thinking: before anything streams in, the hat bobs. */}
        {isThisStreaming && !hasVisible && (
          <div className="flex h-[30px] items-center gap-2.5 text-[14px] text-fg-muted">
            <span className="hat-think inline-grid">
              <Mark size={20} decorative />
            </span>
            Thinking…
          </div>
        )}

        {showCopy && (
          <div className="mt-2 flex items-center gap-0.5 text-fg-subtle">
            <CopyButton text={textContent} size="icon-sm" className="size-[30px] text-fg-subtle" />
            {isLast && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="size-[30px] text-fg-subtle"
                onClick={onRegenerate}
                disabled={isStreaming}
                aria-label="Regenerate"
                title="Regenerate"
              >
                <RotateCw className="size-4" />
              </Button>
            )}
            {timeLabel && (
              <span className="ml-1 font-mono text-[11px] opacity-0 transition-opacity group-hover/msg:opacity-100">
                {timeLabel}
              </span>
            )}
          </div>
        )}
      </div>

      {hasSide && (
        <div className="ai-side min-w-0">
          {citations.length > 0 && (
            <>
              <SourcesHead count={citations.length} />
              <div className="src-row">
                {citations.map((c, i) => (
                  <SourceCard
                    key={`${c.item_id}-${i}`}
                    citation={c}
                    index={i}
                    messageId={message.id}
                  />
                ))}
              </div>
            </>
          )}
          {alsoViewed.length > 0 && <AlsoSearched items={alsoViewed} />}
          {usage && (
            <div className="mt-2.5">
              <UsageFooter usage={usage} />
            </div>
          )}
        </div>
      )}

      {showFollowups && (
        <div className="ai-followups mb-2 mt-[18px] flex flex-wrap gap-2">
          {FOLLOWUPS.map((f) => (
            <button
              key={f}
              onClick={() => onFollowup(f)}
              disabled={isStreaming}
              className="inline-flex min-h-[34px] items-center gap-2 rounded-full border border-border px-3.5 py-1 text-left text-[14px] text-fg-muted transition-colors hover:border-border-strong hover:bg-surface hover:text-fg disabled:opacity-50"
            >
              <ChevronRight className="size-3.5 shrink-0 text-fg-subtle" />
              {f}
            </button>
          ))}
        </div>
      )}
    </div>
  );
});

function SourcesHead({ count }: { count: number }) {
  return (
    <div className="src-head mb-2.5 mt-[22px] flex items-center gap-2.5 font-mono text-[11px] font-medium uppercase leading-none tracking-[0.08em] text-fg-subtle after:h-px after:flex-1 after:bg-border">
      Sources · {count}
    </div>
  );
}

/**
 * A user turn: the bubble, its timestamp, and hover actions (copy + edit). Edit
 * swaps the bubble for an inline textarea; saving re-runs the conversation from
 * that turn via `onEdit`.
 */
function UserMessage({
  text,
  fresh,
  timeLabel,
  disabled,
  onEdit,
}: {
  text: string;
  fresh?: boolean;
  timeLabel: string;
  disabled: boolean;
  onEdit?: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);

  const save = () => {
    const next = draft.trim();
    setEditing(false);
    if (next && next !== text) onEdit?.(next);
  };

  if (editing) {
    return (
      <div className="msg-user flex flex-col items-end">
        <div className="w-full max-w-[min(78%,560px)] rounded-[20px] border border-border-strong bg-surface-2 p-2">
          <AutoGrowTextarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                save();
              } else if (e.key === "Escape") {
                e.preventDefault();
                setEditing(false);
              }
            }}
            className="max-h-60 min-h-[40px] w-full bg-transparent px-2 py-1 text-[16px] text-fg outline-none"
          />
          <div className="flex justify-end gap-1.5 px-1 pt-1">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={save} disabled={!draft.trim()}>
              Save &amp; submit
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("msg-user group flex flex-col items-end gap-1", fresh && "m-sent")}>
      <div className="max-w-[min(78%,560px)] whitespace-pre-wrap rounded-[20px_20px_6px_20px] border border-border bg-surface-2 px-4 py-[11px] text-[16px] leading-[25px] text-fg">
        {text}
      </div>
      <div className="flex items-center gap-0.5 px-1">
        {timeLabel && (
          <span className="font-mono text-[11px] text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100">
            {timeLabel}
          </span>
        )}
        {onEdit && (
          <div className="flex items-center opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
            <CopyButton text={text} size="icon-sm" className="size-6 text-fg-subtle" />
            <Button
              variant="ghost"
              size="icon-sm"
              className="size-6 text-fg-subtle"
              onClick={() => {
                setDraft(text);
                setEditing(true);
              }}
              disabled={disabled}
              aria-label="Edit message"
            >
              <Pencil className="size-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * A run of reasoning + tool calls folded into ONE summary line (mockup
 * `.work`): "Searching your library… 3s" while working, then "✓ Searched
 * library · read 2 sources · 6s". Expanding reveals each reasoning text and
 * tool call (each tool keeps its own result expansion). Opens while the turn
 * streams so steps appear live, folds when it settles — still toggleable.
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
  // Flip `open` to match `streaming` only on the transition, so a manual
  // toggle between transitions sticks ("adjust state on prop change").
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
  const summary = workSummary(streaming, toolParts);

  return (
    <div className="mb-3.5">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex h-[30px] max-w-full items-center gap-2 rounded-full border border-border pl-2.5 pr-3 text-[13px] text-fg-muted transition-colors hover:border-border-strong hover:text-fg"
      >
        {streaming ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-fg-subtle" />
        ) : (
          <Check className="size-3.5 shrink-0 text-success" strokeWidth={2.5} />
        )}
        <span className="truncate">{summary}</span>
        {seconds != null && (
          <span className="shrink-0 font-mono text-[11px] text-fg-subtle">{seconds}s</span>
        )}
        <ChevronDown
          className={cn("size-3.5 shrink-0 transition-transform duration-200", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="mt-2.5 space-y-2 border-l-2 border-border py-1 pl-3.5">
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

/** The one-line label for a `WorkTrace`: what the agent did, in plain words. */
function workSummary(streaming: boolean, toolParts: AnyPart[]): string {
  if (streaming) {
    const active =
      [...toolParts]
        .reverse()
        .find((p) => p.state !== "output-available" && p.state !== "output-error") ??
      toolParts[toolParts.length - 1];
    return `${active ? streamingVerb(toolName(active)) : "Thinking"}…`;
  }
  const count = (names: string[]) =>
    toolParts.filter((p) => names.includes(toolName(p))).length;
  const searches = count(["search_library"]);
  const reads = count(["get_item"]);
  const browses = count(["browse_library", "list_tags", "list_source_types"]);
  const webs = count(["web_search"]);
  const other = toolParts.length - searches - reads - browses - webs;
  const bits: string[] = [];
  if (searches) bits.push(searches > 1 ? `Searched library ×${searches}` : "Searched library");
  if (browses) bits.push("browsed library");
  if (reads) bits.push(`read ${reads} source${reads === 1 ? "" : "s"}`);
  if (webs) bits.push(webs > 1 ? `searched the web ×${webs}` : "searched the web");
  if (other) bits.push(`${other} other step${other === 1 ? "" : "s"}`);
  if (!bits.length) return "Thought it through";
  const s = bits.join(" · ");
  return s[0].toUpperCase() + s.slice(1);
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
    case "web_search":
      return "Searching the web";
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

/** Items a tool surfaced but the answer didn't cite — a quiet disclosure under
 * the sources (mockup `.also`). */
function AlsoSearched({ items }: { items: Citation[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 text-[13px] text-fg-subtle transition-colors hover:text-fg-muted"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        Also searched {items.length} {items.length === 1 ? "source" : "sources"}
      </button>
      {open && (
        <div className="src-row mt-2">
          {items.map((c, i) => (
            <SourceCard key={`${c.item_id}-${i}`} citation={c} index={i} />
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
        <Icon className={cn("size-3.5", failed ? "text-fail" : "text-fg-subtle")} />
        <span className="font-mono text-fg-muted">{name}</span>
        {argSummary && (
          <span className="min-w-0 flex-1 truncate font-mono text-fg-subtle">({argSummary})</span>
        )}
        {!done ? (
          <span className="ml-auto flex items-center gap-1 text-fg-subtle">
            <span className="size-1.5 animate-pulse rounded-full bg-signal" /> running
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
