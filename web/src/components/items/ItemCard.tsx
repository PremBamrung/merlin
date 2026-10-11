import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { useItemHref } from "@/hooks/useItemHref";
import { ImageOff, Star } from "lucide-react";
import type { ListItem } from "@/lib/api/endpoints";
import { StatusDot } from "@/components/common/StatusDot";
import { Highlight } from "@/components/common/Highlight";
import { normalizeSummary } from "@/lib/summary";
import {
  relDate,
  formatDuration,
  shortText,
  stripMarkdown,
  thumbnailUrl,
} from "@/lib/format";
import { usePrefetchItem } from "@/hooks/useItems";
import { vtThumb, vtTitle } from "@/lib/viewTransition";
import { setMorphOrigin } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** A thumbnail with a 16:9 crop, the duration, the saved ★, and a graceful
 *  no-image fallback (mockup `.gc .thumb`). */
function Thumb({ item }: { item: ListItem }) {
  const src = thumbnailUrl(item);
  const duration = formatDuration(item.duration);
  return (
    <div className="m-thumb relative aspect-video w-full overflow-hidden rounded-[10px] bg-surface-2 shadow-[0_1px_0_rgb(255_255_255/0.03)_inset,0_1px_2px_rgb(0_0_0/0.4)]">
      {src ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          // Flies into the Reader's thumbnail. Only ever one visible element per
          // name — see lib/viewTransition.ts.
          style={{ viewTransitionName: vtThumb(item.id) }}
          className="m-img size-full object-cover"
        />
      ) : (
        <div className="flex size-full items-center justify-center text-fg-subtle">
          <ImageOff className="size-6" strokeWidth={1.5} />
        </div>
      )}
      {item.saved_at && (
        <span className="absolute right-2 top-2 grid size-[26px] place-items-center rounded-full bg-black/60 text-signal">
          <Star className="size-3.5 fill-signal" strokeWidth={2} />
          <span className="sr-only">Saved</span>
        </span>
      )}
      {item.status === "failed" && (
        <span className="absolute left-2 top-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-fail">
          Failed
        </span>
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
 * A Library card (mockup `.gc`): the thumbnail, then the title — a gold dot
 * when it's unread — and one mono meta line (topic · channel · date). Opens
 * the item (drawer on desktop, Reader on phones). `snippet` adds two lines of
 * summary (the comfortable density); `dense` tightens type for compact.
 */
export function ItemCard({
  item,
  dense,
  snippet,
  highlight,
  focused,
}: {
  item: ListItem;
  dense?: boolean;
  snippet?: boolean;
  highlight?: string;
  focused?: boolean;
}) {
  const topic = item.topics?.find((t) => t.is_primary)?.label ?? item.topics?.[0]?.label;
  const channel = item.channel ?? item.author;
  const date = relDate(item.published_at ?? item.ingested_at);
  const isFailed = item.status === "failed";
  const ref = useRef<HTMLAnchorElement>(null);
  const prefetch = usePrefetchItem();
  const open = useItemHref()(item.id);

  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "nearest" });
  }, [focused]);

  return (
    <Link
      ref={ref}
      {...open}
      // The card → Reader morph is for the full page; the drawer slides in.
      viewTransition={typeof open.to === "string"}
      onMouseEnter={() => prefetch(item.id)}
      onFocus={() => prefetch(item.id)}
      onClick={(e) => setMorphOrigin(e.currentTarget.querySelector("img"))}
      className={cn(
        "m-lift group block rounded-xl text-fg transition-transform duration-200 ease-[cubic-bezier(0.2,0,0,1)] [@media(pointer:fine)]:hover:-translate-y-0.5",
        focused && "ring-2 ring-signal/50 ring-offset-4 ring-offset-bg",
      )}
    >
      <Thumb item={item} />
      <h3
        style={{ viewTransitionName: vtTitle(item.id) }}
        className={cn(
          "mx-0.5 mb-1 mt-2.5 flex gap-2 font-medium",
          dense ? "text-[13px] leading-[18px]" : "text-[14px] leading-5 sm:text-[14.5px]",
        )}
      >
        {!item.read_at && !isFailed && (
          <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-signal" aria-label="Unread" />
        )}
        <span className="line-clamp-2">
          <Highlight text={item.title ?? "Untitled"} term={highlight} />
        </span>
      </h3>
      <p className="mx-0.5 flex gap-2.5 overflow-hidden whitespace-nowrap font-mono text-[11px] leading-4 text-fg-subtle">
        {topic && <span className="min-w-0 truncate text-ui-eyebrow">{topic}</span>}
        {channel && <span className="min-w-0 truncate">{channel}</span>}
        {date && <span className="hidden shrink-0 sm:inline">{date}</span>}
      </p>
      {snippet && (item.summary || isFailed) && (
        <p className="mx-0.5 mt-2 line-clamp-2 text-[12.5px] leading-snug text-fg-muted">
          {isFailed ? (
            (item.error_message ?? "Ingest failed.")
          ) : (
            <Highlight text={shortText(cleanSnippet(item.summary), 160)} term={highlight} />
          )}
        </p>
      )}
    </Link>
  );
}

/** A card snippet is plain prose: no markdown, no "Overview" label. */
function cleanSnippet(summary: string | null | undefined): string {
  return stripMarkdown(normalizeSummary(summary));
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
  const open = useItemHref()(item.id);

  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: "nearest" });
  }, [focused]);

  return (
    <Link
      ref={ref}
      {...open}
      // The card → Reader morph is for the full page; the drawer slides in.
      viewTransition={typeof open.to === "string"}
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
