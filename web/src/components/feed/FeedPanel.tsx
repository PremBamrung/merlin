import { PanelSlot } from "@/components/layout/panel";
import { PanelSection } from "@/components/layout/PanelParts";
import type { ListItem } from "@/lib/api/endpoints";
import { formatDuration, thumbnailUrl } from "@/lib/format";
import { cn } from "@/lib/utils";

const UNCATEGORISED = "uncategorised";
/** The queue is paged in as you read; the panel shows a window of it. */
const UP_NEXT = 40;

type TopicChip = { slug: string; label: string; count: number };

/**
 * The Feed place's context panel (mockup `feedPanel`): the topic slice as
 * chips, then the up-next queue. A row jumps the reader straight to that card.
 */
export function FeedPanel({
  total,
  topic,
  onTopic,
  topics,
  uncategorised,
  queue,
  index,
  onJump,
}: {
  total: number;
  topic: string | null;
  onTopic: (t: string | null) => void;
  topics: TopicChip[];
  uncategorised: number;
  queue: ListItem[];
  index: number;
  onJump: (i: number) => void;
}) {
  const select = (slug: string) => onTopic(topic === slug ? null : slug);
  const upNext = queue.slice(index, index + UP_NEXT);

  return (
    <PanelSlot title="Feed" sub={`${total} unread`}>
      <div className="flex flex-wrap gap-1.5 pb-2.5 pt-0.5">
        <Chip on={topic === null} onClick={() => onTopic(null)} count={topic === null ? total : undefined} gold>
          All
        </Chip>
        {uncategorised > 0 && (
          <Chip on={topic === UNCATEGORISED} onClick={() => select(UNCATEGORISED)} count={uncategorised}>
            Uncategorised
          </Chip>
        )}
        {topics.map((t) => (
          <Chip key={t.slug} on={topic === t.slug} onClick={() => select(t.slug)} count={t.count}>
            {t.label}
          </Chip>
        ))}
      </div>

      <PanelSection title={`Up next · ${Math.max(0, total - index)}`}>
        {upNext.length === 0 && (
          <p className="px-2.5 py-1 text-[13px] leading-5 text-fg-muted">
            Nothing left. New videos land here as they're added.
          </p>
        )}
        {upNext.map((it, i) => {
          const on = i === 0;
          const thumb = thumbnailUrl(it);
          return (
            <button
              key={it.id}
              onClick={() => onJump(index + i)}
              aria-current={on ? "true" : undefined}
              className={cn(
                "grid w-full grid-cols-[76px_minmax(0,1fr)] items-start gap-2.5 rounded-[10px] px-2 py-[7px] text-left transition-colors",
                on
                  ? "bg-ui-selected-bg text-fg shadow-[inset_2px_0_0_var(--color-ui-selected-bar)]"
                  : "text-fg-muted hover:bg-surface hover:text-fg",
              )}
            >
              <span className="aspect-video overflow-hidden rounded-md bg-surface-2">
                {thumb && <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />}
              </span>
              <span className="min-w-0">
                <span className="flex gap-1.5 text-[13px] font-medium leading-[17px]">
                  {!it.read_at && <span className="mt-[5px] size-1.5 shrink-0 rounded-full bg-signal" />}
                  <span className="line-clamp-2">{it.title}</span>
                </span>
                <span className="mt-[3px] block truncate font-mono text-[10.5px] leading-[15px] text-fg-subtle">
                  {[it.channel, formatDuration(it.duration)].filter(Boolean).join(" · ")}
                </span>
              </span>
            </button>
          );
        })}
      </PanelSection>
    </PanelSlot>
  );
}

function Chip({
  on,
  onClick,
  count,
  gold,
  children,
}: {
  on: boolean;
  onClick: () => void;
  count?: number;
  gold?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={on}
      className={cn(
        "inline-flex h-[26px] items-center gap-1.5 rounded-full border px-2.5 text-[12.5px] transition-colors",
        on
          ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
          : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
      )}
    >
      {children}
      {count != null && (
        <span className={cn("font-mono text-[11px] tabular-nums", gold ? "text-signal" : "text-fg-subtle")}>
          {count}
        </span>
      )}
    </button>
  );
}
