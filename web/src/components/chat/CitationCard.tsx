import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { Citation } from "@/lib/api/client";

export function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  return (
    <Link
      to={`/library/${citation.item_id}`}
      className="group flex items-start gap-2.5 rounded-[10px] border border-border bg-surface px-3 py-2.5 transition-colors hover:border-border-strong"
    >
      <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-accent-subtle font-mono text-[11px] text-accent">
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
