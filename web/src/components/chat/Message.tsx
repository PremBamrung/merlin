import { useState } from "react";
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
} from "lucide-react";
import type { UIMessage } from "ai";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/common/Markdown";
import { CopyButton } from "@/components/common/CopyButton";
import { CitationCard } from "@/components/chat/CitationCard";
import type { Citation } from "@/hooks/useAgentChat";
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
  data?: { items?: Citation[] };
};

function isToolPart(p: AnyPart): boolean {
  return p.type === "dynamic-tool" || p.type.startsWith("tool-");
}

function toolName(p: AnyPart): string {
  return p.toolName ?? (p.type.startsWith("tool-") ? p.type.slice(5) : "tool");
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
  const textContent = parts
    .filter((p) => p.type === "text")
    .map((p) => p.text ?? "")
    .join("");

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[14px] rounded-tr-sm bg-surface-2 px-4 py-2.5 text-[14px] text-fg">
          {textContent}
        </div>
      </div>
    );
  }

  // Consolidated citations arrive as a `data-citations` part.
  const citations: Citation[] = parts
    .filter((p) => p.type === "data-citations")
    .flatMap((p) => p.data?.items ?? []);

  const isThisStreaming = isStreaming && isLast;
  const hasVisible = parts.some(
    (p) => (p.type === "text" && p.text) || p.type === "reasoning" || isToolPart(p),
  );
  const showActions = isLast && !isThisStreaming && !!textContent;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-accent">✦</span>
        <span className="eyebrow">Merlin</span>
      </div>

      <div className="space-y-2.5">
        {parts.map((p, i) => {
          if (p.type === "reasoning" && p.text) {
            return <ReasoningBlock key={i} text={p.text} />;
          }
          if (isToolPart(p)) {
            return <ToolTrace key={i} part={p} />;
          }
          if (p.type === "text" && p.text) {
            return (
              <div key={i} className="max-w-none">
                <Markdown>{p.text}</Markdown>
              </div>
            );
          }
          return null;
        })}

        {/* Thinking placeholder before any content streams in. */}
        {isThisStreaming && !hasVisible && (
          <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-fg-muted align-middle" />
        )}
      </div>

      {citations.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="eyebrow">Sources</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {citations.map((c, i) => (
              <CitationCard key={`${c.item_id}-${i}`} citation={c} index={i} />
            ))}
          </div>
        </div>
      )}

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

/** A collapsible reasoning trace (shown when the model emits reasoning parts). */
function ReasoningBlock({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-[10px] border border-border bg-surface-2/50">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[12px] text-fg-muted"
      >
        <Brain className="size-3.5 text-fg-subtle" />
        <span className="eyebrow">Thinking</span>
        <ChevronRight className={cn("ml-auto size-3.5 transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <div className="border-t border-border px-3 py-2 text-[12.5px] italic leading-relaxed text-fg-muted">
          {text}
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
