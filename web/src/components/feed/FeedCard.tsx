import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Star,
  MonitorPlay,
  FileText,
  MessageSquare,
  Globe,
  type LucideIcon,
} from "lucide-react";
import { Markdown } from "@/components/common/Markdown";
import { Button } from "@/components/ui/button";
import type { ListItem } from "@/lib/api/endpoints";
import { formatDuration, relDate, thumbnailUrl } from "@/lib/format";
import { detailRows } from "@/lib/itemDetails";
import { cn } from "@/lib/utils";

/**
 * The gold-leaf save — one of exactly two state-tied motion moments in the app
 * (the other is the ingest ring on the mark). It fires on the *transition* into
 * saved, never on mount: a card that is already saved must not pop when you
 * swipe onto it. Unsaving is silent — taking something back doesn't deserve a
 * flourish. `prefers-reduced-motion` neutralises it globally.
 */
function SaveStar({ saved }: { saved: boolean }) {
  const wasSaved = useRef(saved);
  const [leafing, setLeafing] = useState(false);

  useEffect(() => {
    const justSaved = saved && !wasSaved.current;
    wasSaved.current = saved;
    if (!justSaved) return;
    setLeafing(true);
    const t = window.setTimeout(() => setLeafing(false), 400);
    return () => window.clearTimeout(t);
  }, [saved]);

  return (
    <Star
      className={cn("size-4", saved && "fill-signal", leafing && "gold-leaf")}
    />
  );
}

const SOURCE_ICON: Record<string, LucideIcon> = {
  youtube: MonitorPlay,
  reddit: MessageSquare,
  pdf: FileText,
  article: Globe,
};

/**
 * A single lean reading card: thumbnail + source chip + title + one meta line,
 * then the summary as a scrollable body. The footer pages between cards and
 * carries the ★ save + ↗ full-reader escape hatch. Everything else lives in
 * the Reader.
 */
export function FeedCard({
  item,
  position,
  total,
  saved,
  onSave,
  onPrev,
  onNext,
  hasPrev,
}: {
  item: ListItem;
  position: number;
  total: number;
  saved: boolean;
  onSave: () => void;
  onPrev: () => void;
  onNext: () => void;
  hasPrev: boolean;
}) {
  const Icon = SOURCE_ICON[item.source_type] ?? Globe;
  const thumb = thumbnailUrl(item);
  const meta = [
    item.channel ?? item.author,
    formatDuration(item.duration),
    relDate(item.ingested_at),
  ].filter(Boolean);
  const rows = detailRows(item);

  return (
    <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-xl shadow-black/20">
      {/* Reading region — one scroll on mobile; two independent columns on
          wide screens (media + meta left, summary right) so desktop space
          isn't wasted on a narrow centered column. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain lg:flex-row lg:overflow-hidden">
        {/* Media + meta: full-width header on mobile, fixed left rail on desktop */}
        <div className="lg:w-[380px] lg:shrink-0 lg:overflow-y-auto lg:border-r lg:border-border">
          {thumb && (
            <div className="aspect-video w-full overflow-hidden bg-surface-2">
              <img
                src={thumb}
                alt=""
                draggable={false}
                className="size-full object-cover"
              />
            </div>
          )}
          <div className="px-5 py-6 sm:px-8 sm:py-7 lg:px-7">
            <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wide text-fg-subtle">
              <Icon className="size-3.5" strokeWidth={1.5} />
              <span>{item.source_type}</span>
            </div>

            <h1 className="mt-3 text-balance font-display text-[24px] font-semibold leading-tight tracking-tight sm:text-[28px] lg:text-[24px]">
              {item.title ?? "Untitled"}
            </h1>

            {meta.length > 0 && (
              <p className="mt-2 flex flex-wrap items-center gap-x-2 text-[12.5px] text-fg-muted">
                {meta.map((m, i) => (
                  <span key={i} className="flex items-center gap-2">
                    {i > 0 && <span className="text-border-strong">·</span>}
                    {m}
                  </span>
                ))}
              </p>
            )}

            {/* Details — open on desktop (fills the rail), collapsible on mobile */}
            <div className="mt-6 hidden lg:block">
              <p className="eyebrow mb-2">Details</p>
              <DetailList rows={rows} />
            </div>
            <details className="group mt-5 lg:hidden">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[12px] font-medium text-fg-muted [&::-webkit-details-marker]:hidden">
                <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
                Details
              </summary>
              <div className="mt-3">
                <DetailList rows={rows} />
              </div>
            </details>
          </div>
        </div>

        {/* Summary — fills the rest of the width, capped to a readable measure */}
        <div className="min-h-0 lg:flex-1 lg:overflow-y-auto">
          <div className="mx-auto max-w-[72ch] px-5 pb-8 sm:px-8 lg:px-10 lg:py-8">
            {item.summary ? (
              <Markdown>{item.summary}</Markdown>
            ) : (
              <p className="text-[14px] text-fg-muted">No summary for this item.</p>
            )}
          </div>
        </div>
      </div>

      {/* Footer: save · pager · full reader. Sits in thumb reach on mobile. */}
      <footer className="flex items-center justify-between gap-2 border-t border-border bg-surface/80 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
        <Button
          variant="ghost"
          size="sm"
          onClick={onSave}
          aria-pressed={saved}
          aria-label={saved ? "Unsave" : "Save"}
          className={cn(saved && "text-signal")}
        >
          <SaveStar saved={saved} />
          <span className="hidden sm:inline">{saved ? "Saved" : "Save"}</span>
        </Button>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onPrev}
            disabled={!hasPrev}
            aria-label="Previous"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="min-w-[3.5rem] text-center font-mono text-[12px] tabular-nums text-fg-subtle">
            {position} / {total}
          </span>
          <Button variant="ghost" size="icon-sm" onClick={onNext} aria-label="Next">
            <ChevronRight className="size-4" />
          </Button>
        </div>

        <Button variant="ghost" size="sm" asChild>
          <Link to={`/library/${item.id}`}>
            <ExternalLink className="size-4" />
            <span className="hidden sm:inline">Full reader</span>
          </Link>
        </Button>
      </footer>
    </article>
  );
}

/** The key/value Details panel (shared shape with the Reader's rail). */
function DetailList({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="space-y-2 rounded-[10px] border border-border bg-surface-2/40 p-3.5">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-3">
          <dt className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-fg-subtle">
            {label}
          </dt>
          <dd className="truncate text-right text-[12.5px] text-fg-muted">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
