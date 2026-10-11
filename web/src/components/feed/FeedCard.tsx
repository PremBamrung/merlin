import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Check, ExternalLink, MessageSquare, Star, X } from "lucide-react";
import { Markdown } from "@/components/common/Markdown";
import { Button } from "@/components/ui/button";
import type { ListItem } from "@/lib/api/endpoints";
import { formatDuration, relDate, thumbnailUrl, youtubeUrl } from "@/lib/format";
import { normalizeSummary } from "@/lib/summary";
import { cn } from "@/lib/utils";

/**
 * The gold-leaf save — one of exactly two state-tied motion moments in the app
 * (the other is the ingest ring on the mark). It fires on the *transition* into
 * saved, never on mount: a card that is already saved must not pop when you
 * swipe onto it. Unsaving is silent — taking something back doesn't deserve a
 * flourish. `prefers-reduced-motion` neutralises it globally.
 */
export function SaveStar({ saved, className }: { saved: boolean; className?: string }) {
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

  return <Star className={cn("size-4", saved && "fill-signal", leafing && "gold-leaf", className)} />;
}

/** Summary reading time, from its own word count (not the transcript's). */
function readMinutes(markdown: string): number {
  return Math.max(1, Math.round(markdown.split(/\s+/).filter(Boolean).length / 220));
}

/**
 * The Feed's split reader card (docs/EVERYDAY_AI_PLAN.md § Feed; mockup
 * `.fcard.split`). From `lg`: thumbnail, topic, title, meta, tags and the
 * Watch / Ask actions on the left; the FULL summary on the right, scrolling
 * inside the card, with a fade while there's more below. Below `lg` it stacks
 * and the whole card scrolls. Paging and read/save live in <FeedActions>.
 */
export function FeedCard({ item }: { item: ListItem }) {
  const thumb = thumbnailUrl(item);
  const watch = item.source_type === "youtube" ? youtubeUrl(item.source_id) : null;
  const topic = item.topics?.find((t) => t.is_primary)?.label ?? item.topics?.[0]?.label;
  const duration = formatDuration(item.duration);
  const meta = [item.channel ?? item.author, relDate(item.published_at ?? item.ingested_at), duration].filter(
    Boolean,
  );
  const summary = normalizeSummary(item.summary);

  // The fade under the summary says "there's more" — gone once you reach it.
  const scrollRef = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState(false);
  const measure = () => {
    const el = scrollRef.current;
    if (el) setMore(el.scrollHeight - el.scrollTop - el.clientHeight > 8);
  };
  useEffect(measure, [item.id]);

  return (
    <article className="relative z-[3] flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain rounded-[18px] border border-border-strong bg-surface shadow-[0_24px_60px_rgb(0_0_0/0.45)] lg:grid lg:grid-cols-[minmax(300px,2fr)_minmax(0,3fr)] lg:overflow-hidden min-[1900px]:grid-cols-[minmax(340px,5fr)_minmax(0,7fr)]">
      <div className="flex min-w-0 flex-col p-4 sm:p-[22px] lg:overflow-y-auto lg:border-r lg:border-border min-[1900px]:p-7">
        {thumb && (
          <div className="relative aspect-video overflow-hidden rounded-xl bg-surface-2 shadow-[0_1px_2px_rgb(0_0_0/0.4)]">
            <img src={thumb} alt="" draggable={false} className="size-full object-cover" />
            {duration && (
              <span className="absolute bottom-2 right-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] text-white">
                {duration}
              </span>
            )}
          </div>
        )}
        <div className="mt-[18px] min-w-0">
          {topic && <p className="eyebrow !text-ui-eyebrow">{topic}</p>}
          <h1 className="my-2 text-balance font-display text-[20px] font-semibold leading-[26px] tracking-[-0.02em] sm:text-[24px] sm:leading-[31px] min-[1900px]:text-[28px] min-[1900px]:leading-[35px]">
            {item.title ?? "Untitled"}
          </h1>
          {meta.length > 0 && (
            <p className="flex flex-wrap gap-x-3 font-mono text-[12px] leading-[18px] text-fg-subtle">
              {meta.map((m, i) => (
                <span key={i}>{m}</span>
              ))}
            </p>
          )}
          {(item.tags?.length ?? 0) > 0 && (
            <div className="mt-3.5 flex flex-wrap gap-1.5">
              {item.tags!.map((t) => (
                <span
                  key={t}
                  className="inline-flex h-6 items-center rounded-full border border-border px-2.5 font-mono text-[11.5px] leading-none text-fg-subtle"
                >
                  #{t}
                </span>
              ))}
            </div>
          )}
          <div className="mt-[18px] flex flex-wrap gap-2">
            {watch && (
              <Button variant="ghost" size="sm" asChild>
                <a href={watch} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-3.5" /> Watch on YouTube
                </a>
              </Button>
            )}
            <Button variant="outline" size="sm" asChild>
              <Link to={`/library/${item.id}`}>
                <MessageSquare className="size-3.5" /> Ask about this
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="relative min-h-0 min-w-0">
        <div
          ref={scrollRef}
          onScroll={measure}
          className="px-[18px] pb-[22px] pt-3.5 sm:px-9 sm:pb-[34px] sm:pt-[26px] lg:h-full lg:overflow-y-auto lg:overscroll-contain min-[1900px]:px-12 min-[1900px]:pb-10 min-[1900px]:pt-8"
        >
          <div className="mb-3.5 flex justify-between gap-3 font-mono text-[11px] font-medium uppercase leading-none tracking-[0.08em] text-fg-subtle">
            <span>Summary</span>
            {summary && <span>{readMinutes(summary)} min read</span>}
          </div>
          {summary ? (
            <Markdown className="max-w-[78ch] text-fg [&>:first-child]:mt-0 [&_h2]:mb-3 [&_h2]:mt-[26px] [&_h2]:font-mono [&_h2]:text-[11px] [&_h2]:font-medium [&_h2]:uppercase [&_h2]:leading-none [&_h2]:tracking-[0.08em] [&_h2]:text-fg-subtle [&_li]:mb-2.5 [&_li]:pl-1 [&_li]:text-fg-muted [&_li::marker]:font-mono [&_li::marker]:text-[12px] [&_li::marker]:text-fg-subtle [&_ol]:pl-[22px] [&_p]:text-fg [&_ul]:pl-[22px] min-[1900px]:text-[17px] min-[1900px]:leading-[29px]">
              {summary}
            </Markdown>
          ) : (
            <p className="text-[14px] text-fg-muted">No summary for this item.</p>
          )}
        </div>
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-x-0 bottom-0 right-2.5 hidden h-16 rounded-br-[18px] bg-linear-to-b from-transparent to-surface transition-opacity duration-200 lg:block",
            more ? "opacity-100" : "opacity-0",
          )}
        />
      </div>
    </article>
  );
}

/** The round actions under the card (mockup `.feed-actions`) + key hints. */
export function FeedActions({
  saved,
  onSkip,
  onSave,
  onRead,
  onAsk,
}: {
  saved: boolean;
  onSkip: () => void;
  onSave: () => void;
  onRead: () => void;
  onAsk: () => void;
}) {
  const round =
    "grid size-12 place-items-center rounded-full border border-border-strong bg-surface text-fg-muted transition-[transform,background,color] duration-150 hover:bg-surface-2 hover:text-fg sm:size-[54px] [@media(pointer:fine)]:hover:scale-[1.06]";
  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center gap-3.5">
        <button onClick={onSkip} className={round} aria-label="Skip (←)" title="Skip — keep it unread (←)">
          <X className="size-5" />
        </button>
        <button
          onClick={onSave}
          className={cn(round, "text-signal hover:text-signal")}
          aria-pressed={saved}
          aria-label={saved ? "Unsave (S)" : "Save (S)"}
          title={saved ? "Saved (S)" : "Save (S)"}
        >
          <SaveStar saved={saved} className="size-5" />
        </button>
        <button
          onClick={onRead}
          className={cn(round, "size-14 border-transparent bg-ui-primary text-ui-primary-fg hover:bg-ui-primary-hover hover:text-ui-primary-fg sm:size-[62px]")}
          aria-label="Read — next (→)"
          title="Mark read and go on (→)"
        >
          <Check className="size-6" strokeWidth={2.4} />
        </button>
        <button onClick={onAsk} className={round} aria-label="Ask about this (A)" title="Ask about this (A)">
          <MessageSquare className="size-5" />
        </button>
      </div>
      <div className="mt-3 hidden flex-wrap justify-center gap-4 font-mono text-[11px] leading-4 text-fg-subtle md:flex">
        {[
          ["←", "skip"],
          ["S", "save"],
          ["→", "read"],
          ["A", "ask"],
        ].map(([k, label]) => (
          <span key={k} className="flex items-center gap-1.5">
            <kbd className="rounded border border-border-strong px-1.5 py-0.5 text-[10px] leading-none">{k}</kbd>
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
