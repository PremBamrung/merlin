import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { citeAnchorId, type Citation } from "@/hooks/useAgentChat";

export function CitationCard({
  citation,
  index,
  messageId,
}: {
  citation: Citation;
  index: number;
  /** When set, the card is a scroll target for inline citation chips. */
  messageId?: string;
}) {
  return (
    <Link
      id={messageId ? citeAnchorId(messageId, citation.item_id) : undefined}
      to={`/library/${citation.item_id}`}
      className="group flex scroll-mt-6 items-start gap-2.5 rounded-[10px] border border-border bg-surface px-3 py-2.5 transition-colors hover:border-border-strong"
    >
      <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-accent-subtle font-mono text-[11px] text-accent-lit">
        {index + 1}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1 text-[13px] font-medium text-fg">
          <span className="truncate">{citation.title}</span>
          <ArrowUpRight className="size-3.5 shrink-0 text-fg-subtle transition-colors group-hover:text-fg" />
        </p>
        {citation.snippet && (
          <p className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-fg-muted">
            {citation.snippet}
          </p>
        )}
      </div>
    </Link>
  );
}
