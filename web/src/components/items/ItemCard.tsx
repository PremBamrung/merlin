import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ImageOff } from "lucide-react";
import type { ListItem } from "@/lib/api/endpoints";
import { StatusDot } from "@/components/common/StatusDot";
import { Highlight } from "@/components/common/Highlight";
import { Badge } from "@/components/ui/badge";
import {
  relDate,
  formatDuration,
  shortText,
  stripMarkdown,
  thumbnailUrl,
} from "@/lib/format";
import { usePrefetchItem } from "@/hooks/useItems";
import { vtThumb, vtTitle } from "@/lib/viewTransition";
import { cn } from "@/lib/utils";

/** A thumbnail with a 16:9 crop and a graceful no-image fallback. */
function Thumb({ item }: { item: ListItem }) {
  const src = thumbnailUrl(item);
  const duration = formatDuration(item.duration);
  return (
    <div className="relative aspect-video w-full overflow-hidden bg-surface-2">
      {src ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          // Flies into the Reader's thumbnail. Only ever one visible element per
          // name — see lib/viewTransition.ts.
          style={{ viewTransitionName: vtThumb(item.id) }}
          className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
        />
      ) : (
        <div className="flex size-full items-center justify-center text-fg-subtle">
          <ImageOff className="size-6" strokeWidth={1.5} />
        </div>
      )}
      {duration && (
        <span className="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-white">
          {duration}
        </span>
      )}
    </div>
  );
}

/**
 * Library/Today card: thumbnail, duration, title, mono meta line, status dot,
 * summary snippet, tag pills. Links to the Reader. `dense` drops the snippet.
 */
export function ItemCard({
  item,
  dense,
  highlight,
  focused,
}: {
  item: ListItem;
  dense?: boolean;
  highlight?: string;
  focused?: boolean;
}) {
  const meta = [item.channel ?? item.author, relDate(item.ingested_at)]
    .filter(Boolean)
    .join(" · ");
  const isFailed = item.status === "failed";
  const ref = useRef<HTMLAnchorElement>(null);
  const prefetch = usePrefetchItem();

  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "nearest" });
  }, [focused]);

  return (
    <Link
      ref={ref}
      to={`/library/${item.id}`}
      viewTransition
      onMouseEnter={() => prefetch(item.id)}
      onFocus={() => prefetch(item.id)}
      className={cn(
        "group flex flex-col overflow-hidden rounded-[10px] border border-border bg-surface transition-colors hover:border-border-strong",
        focused && "border-signal/60 ring-2 ring-signal/40",
      )}
    >
      <Thumb item={item} />
      <div className="flex flex-1 flex-col gap-2 p-3">
        {isFailed && <span className="eyebrow text-fail">⛔ Failed</span>}
        <h3
          style={{ viewTransitionName: vtTitle(item.id) }}
          className="line-clamp-2 font-display text-[14px] font-medium leading-snug text-fg"
        >
          <Highlight text={item.title ?? "Untitled"} term={highlight} />
        </h3>

        <div className="flex items-center gap-1.5 text-[11px]">
          <StatusDot status={item.status} />
          <span className="truncate font-mono uppercase tracking-wide text-fg-subtle">
            {meta}
          </span>
        </div>

        {!dense && (item.summary || isFailed) && (
          <p className="line-clamp-2 text-[12.5px] leading-snug text-fg-muted">
            {isFailed ? (
              (item.error_message ?? "Ingest failed.")
            ) : (
              <Highlight
                text={shortText(stripMarkdown(item.summary), 140)}
                term={highlight}
              />
            )}
          </p>
        )}

        {!dense && (item.tags?.length ?? 0) > 0 && (
          <div className="mt-auto flex flex-wrap gap-1 pt-1">
            {item.tags!.slice(0, 3).map((t) => (
              <Badge key={t} variant="outline" className="font-mono text-[10px]">
                #{t}
              </Badge>
            ))}
            {item.tags!.length > 3 && (
              <span className="text-[10px] text-fg-subtle">
                +{item.tags!.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

/** Compact list-row variant of an item (Library list view). */
export function ItemRow({
  item,
  highlight,
  focused,
}: {
  item: ListItem;
  highlight?: string;
  focused?: boolean;
}) {
  const meta = [item.channel ?? item.author, relDate(item.ingested_at)]
    .filter(Boolean)
    .join(" · ");
  const src = thumbnailUrl(item);
  const ref = useRef<HTMLAnchorElement>(null);
  const prefetch = usePrefetchItem();

  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "nearest" });
  }, [focused]);

  return (
    <Link
      ref={ref}
      to={`/library/${item.id}`}
      viewTransition
      onMouseEnter={() => prefetch(item.id)}
      onFocus={() => prefetch(item.id)}
      className={cn(
        "group flex items-center gap-3 rounded-[10px] border border-border bg-surface px-3 py-2.5 transition-colors hover:border-border-strong",
        focused && "border-signal/60 ring-2 ring-signal/40",
      )}
    >
      <div className="relative aspect-video w-28 shrink-0 overflow-hidden rounded-md bg-surface-2">
        {src ? (
          <img src={src} alt="" loading="lazy" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center text-fg-subtle">
            <ImageOff className="size-4" strokeWidth={1.5} />
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <StatusDot status={item.status} />
          <h3
            style={{ viewTransitionName: vtTitle(item.id) }}
            className="truncate font-display text-[14px] font-medium text-fg"
          >
            <Highlight text={item.title ?? "Untitled"} term={highlight} />
          </h3>
        </div>
        <p className="truncate font-mono text-[11px] uppercase tracking-wide text-fg-subtle">
          {meta}
        </p>
      </div>
      <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-subtle">
        {formatDuration(item.duration)}
      </span>
    </Link>
  );
}
