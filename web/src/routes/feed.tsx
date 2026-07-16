import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Inbox as InboxIcon, Sparkles } from "lucide-react";
import { CheckCheck } from "lucide-react";
import {
  useFeedQueue,
  useMarkAllRead,
  useMarkRead,
  useMarkUnread,
  useToggleSaved,
} from "@/hooks/useFeed";
import { useTopics, useUncategorisedCount } from "@/hooks/useTopics";
import { FeedCard } from "@/components/feed/FeedCard";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toaster";
import type { FeedFilter } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

const SWIPE_THRESHOLD = 64; // px of horizontal travel to commit a page-turn
const PREFETCH_AHEAD = 3; // load the next page this many cards before the end
const UNCATEGORISED = "uncategorised"; // sentinel slug for the "no topic" slice

/**
 * Owns the navigation filter (topic slice). The reading stack is a
 * child keyed by the filter signature, so switching filter *remounts* it — a
 * fresh queue, cursor, and read-set with no manual reset (idiomatic React
 * "reset state with a key").
 */
export default function FeedRoute() {
  const [topic, setTopic] = useState<string | null>(null); // slug | sentinel | null
  const filter = useMemo<FeedFilter>(
    () => ({ topics: topic ? [topic] : undefined }),
    [topic],
  );
  const filterSig = topic ?? "";

  const clearFilter = useCallback(() => setTopic(null), []);

  return (
    <FeedReader
      key={filterSig}
      filter={filter}
      filtered={!!topic}
      topic={topic}
      onTopic={setTopic}
      onClearFilter={clearFilter}
    />
  );
}

function FeedReader({
  filter,
  filtered,
  topic,
  onTopic,
  onClearFilter,
}: {
  filter: FeedFilter;
  filtered: boolean;
  topic: string | null;
  onTopic: (t: string | null) => void;
  onClearFilter: () => void;
}) {
  const q = useFeedQueue(filter);
  const topics = useTopics("active", true); // unread-scoped: only topics in the queue
  const uncategorised = useUncategorisedCount(true);
  const markRead = useMarkRead();
  const markUnread = useMarkUnread();
  const markAllRead = useMarkAllRead();
  const toggleSaved = useToggleSaved();
  const [confirmAll, setConfirmAll] = useState(false);

  const queue = useMemo(
    () => q.data?.pages.flatMap((p) => p.items) ?? [],
    [q.data],
  );
  const total = q.data?.pages[0]?.total ?? 0;

  const [index, setIndex] = useState(0);
  const [dragX, setDragX] = useState(0);
  const [readCount, setReadCount] = useState(0);
  // Ids marked read this session — so swiping back doesn't re-fire the mutation.
  const readSet = useRef<Set<string>>(new Set());

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = q;

  // Keep the queue a few cards ahead of the cursor.
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && index >= queue.length - PREFETCH_AHEAD)
      fetchNextPage();
  }, [index, queue.length, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const undoRead = useCallback(
    (id: string, idx: number) => {
      readSet.current.delete(id);
      setReadCount((c) => Math.max(0, c - 1));
      markUnread.mutate(id);
      setIndex(idx);
    },
    [markUnread],
  );

  const markReadOnce = useCallback(
    (id: string) => {
      if (readSet.current.has(id)) return false;
      readSet.current.add(id);
      setReadCount((c) => c + 1);
      markRead.mutate(id);
      return true;
    },
    [markRead],
  );

  const goNext = useCallback(() => {
    const leaving = queue[index];
    const leavingIdx = index;
    if (leaving && markReadOnce(leaving.id)) {
      toast("Marked read", {
        id: "feed-read",
        duration: 4000,
        action: { label: "Undo", onClick: () => undoRead(leaving.id, leavingIdx) },
      });
    }
    if (index < queue.length - 1) setIndex(index + 1);
    else if (hasNextPage) fetchNextPage();
    else setIndex(queue.length);
  }, [queue, index, hasNextPage, fetchNextPage, markReadOnce, undoRead]);

  const goPrev = useCallback(() => {
    setIndex((i) => Math.max(0, Math.min(i, queue.length) - 1));
  }, [queue.length]);

  // ←/→ page through cards (no text inputs live on this route).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev]);

  // --- pointer-based horizontal swipe (touch + mouse) --------------------- //
  const drag = useRef<{ x: number; y: number; axis: "" | "x" | "y" } | null>(null);

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === "mouse") return;
    drag.current = { x: e.clientX, y: e.clientY, axis: "" };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    if (!d.axis) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      d.axis = Math.abs(dx) > Math.abs(dy) ? "x" : "y";
    }
    if (d.axis === "x") setDragX(dx);
  };
  const endDrag = () => {
    const d = drag.current;
    drag.current = null;
    if (d?.axis === "x") {
      if (dragX <= -SWIPE_THRESHOLD) goNext();
      else if (dragX >= SWIPE_THRESHOLD) goPrev();
    }
    setDragX(0);
  };

  const filterBar = (
    <FilterBar
      topic={topic}
      onTopic={onTopic}
      topics={topics.data ?? []}
      uncategorisedCount={uncategorised.data ?? 0}
      total={total}
      onMarkAll={() => setConfirmAll(true)}
      markAllPending={markAllRead.isPending}
    />
  );

  // --- body per state (filter bar stays mounted so you can always re-slice) //
  let body: React.ReactNode;
  if (q.isLoading) {
    body = <ReaderSkeleton />;
  } else if (q.isError) {
    body = <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  } else if (total === 0) {
    body = filtered ? (
      <EmptyState
        icon={InboxIcon}
        title="Nothing in this slice"
        description="No unread items match this filter. Clear it to see the rest of your queue."
        action={
          <Button size="sm" variant="secondary" onClick={onClearFilter}>
            Clear filter
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={InboxIcon}
        title="Nothing to read"
        description="No unread summaries. Ingest something, or browse what you've already read in the Library."
        action={
          <Button asChild size="sm">
            <Link to="/library">Open library</Link>
          </Button>
        }
      />
    );
  } else if (index >= queue.length && !hasNextPage) {
    body = (
      <EmptyState
        icon={CheckCircle2}
        title="You're all caught up"
        description={`Read ${readCount} ${readCount === 1 ? "summary" : "summaries"} this session. New ingests will show up here.`}
        action={
          <Button asChild size="sm" variant="secondary">
            <Link to="/library">Browse library</Link>
          </Button>
        }
      />
    );
  } else {
    const item = queue[Math.min(index, queue.length - 1)];
    body = !item ? (
      <ReaderSkeleton />
    ) : (
      <div
        className={cn(
          "h-full touch-pan-y will-change-transform",
          dragX === 0
            ? "transition-transform duration-200 ease-out motion-reduce:transition-none"
            : "select-none transition-none",
        )}
        style={{ transform: `translateX(${dragX}px)` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <FeedCard
          key={item.id}
          item={item}
          position={Math.min(index + 1, total)}
          total={total}
          saved={!!item.saved_at}
          onSave={() => toggleSaved.mutate({ id: item.id, saved: !item.saved_at })}
          onPrev={goPrev}
          onNext={goNext}
          hasPrev={index > 0}
        />
      </div>
    );
  }

  return (
    <FeedFrame>
      <div className="flex h-full flex-col">
        {filterBar}
        <div className="min-h-0 flex-1">{body}</div>
      </div>

      <Dialog open={confirmAll} onOpenChange={setConfirmAll}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Mark all as read?</DialogTitle>
            <DialogDescription>
              All {total} unread {total === 1 ? "summary" : "summaries"} in this
              view will be marked read and cleared from the Feed. They stay in
              your Library.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => setConfirmAll(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                markAllRead.mutate(undefined, {
                  onSuccess: () => {
                    setConfirmAll(false);
                    setIndex(0);
                  },
                })
              }
              disabled={markAllRead.isPending}
            >
              <CheckCheck className="size-4" /> Mark all read
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </FeedFrame>
  );
}

type TopicChip = { slug: string; label: string; count: number };

function FilterBar({
  topic,
  onTopic,
  topics,
  uncategorisedCount,
  total,
  onMarkAll,
  markAllPending,
}: {
  topic: string | null;
  onTopic: (t: string | null) => void;
  topics: TopicChip[];
  uncategorisedCount: number;
  total: number;
  onMarkAll: () => void;
  markAllPending: boolean;
}) {
  const select = (slug: string) => onTopic(topic === slug ? null : slug);
  return (
    <div className="mb-3 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <p className="eyebrow">{total} unread</p>
        <div className="flex items-center gap-1">
          <Button asChild variant="ghost" size="sm">
            <Link to="/topics">
              <Sparkles className="size-3.5" /> Organise
              {uncategorisedCount > 0 && (
                <span className="ml-1 font-mono text-[11px] tabular-nums text-fg-subtle">
                  {uncategorisedCount}
                </span>
              )}
            </Link>
          </Button>
          <Button variant="ghost" size="sm" onClick={onMarkAll} disabled={markAllPending}>
            <CheckCheck className="size-3.5" /> Mark all read
          </Button>
        </div>
      </div>

      {/* Topic slice chips (single-select). Single-row horizontal scroll on
          mobile so the many topics don't crush the card; wrap on sm+. */}
      <div className="no-scrollbar -mx-4 flex items-center gap-1.5 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
        <FilterChip active={topic === null} onClick={() => onTopic(null)}>
          All
        </FilterChip>
        {uncategorisedCount > 0 && (
          <FilterChip
            active={topic === UNCATEGORISED}
            onClick={() => select(UNCATEGORISED)}
          >
            Uncategorised
            <Count n={uncategorisedCount} />
          </FilterChip>
        )}
        {topics.map((t) => (
          <FilterChip key={t.slug} active={topic === t.slug} onClick={() => select(t.slug)}>
            {t.label}
            <Count n={t.count} />
          </FilterChip>
        ))}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
        active
          ? "border-accent-border bg-accent-subtle text-fg"
          : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function Count({ n }: { n: number }) {
  return (
    <span className="ml-1.5 font-mono text-[10px] tabular-nums text-fg-subtle">
      {n}
    </span>
  );
}

/** Centered reading frame that fills the viewport height; wide on desktop so
 *  the two-column card uses the space instead of a narrow centered column. */
function FeedFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto h-[calc(100vh-8rem)] max-w-[760px] sm:h-[calc(100vh-9rem)] lg:max-w-[1120px]">
      {children}
    </div>
  );
}
