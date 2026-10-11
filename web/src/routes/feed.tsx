import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  CheckCheck,
  CheckCircle2,
  ChevronLeft,
  Inbox as InboxIcon,
  MoreHorizontal,
  Sparkles,
} from "lucide-react";
import {
  useFeedQueue,
  useMarkAllRead,
  useMarkRead,
  useMarkUnread,
  useToggleSaved,
} from "@/hooks/useFeed";
import { useTopics, useUncategorisedCount } from "@/hooks/useTopics";
import { FeedActions, FeedCard } from "@/components/feed/FeedCard";
import { FeedPanel } from "@/components/feed/FeedPanel";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  const navigate = useNavigate();
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

  // Skip = move on but leave it unread (it stays in the queue for next time).
  const goSkip = useCallback(() => {
    if (index < queue.length - 1) setIndex(index + 1);
    else if (hasNextPage) fetchNextPage();
    else setIndex(queue.length);
  }, [index, queue.length, hasNextPage, fetchNextPage]);

  const current = queue[Math.min(index, queue.length - 1)];
  const toggleCurrentSaved = useCallback(() => {
    if (current) toggleSaved.mutate({ id: current.id, saved: !current.saved_at });
  }, [current, toggleSaved]);
  const askCurrent = useCallback(() => {
    if (current) navigate(`/library/${current.id}`);
  }, [current, navigate]);

  // ← skip · → read · S save · A ask (the spec's Feed keys). Not while
  // typing, and not while the item drawer or a dialog owns the keyboard.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
      if (document.querySelector("[role='dialog']")) return;
      const k = e.key.toLowerCase();
      if (e.key === "ArrowRight") goNext();
      else if (e.key === "ArrowLeft") goSkip();
      else if (k === "s") toggleCurrentSaved();
      else if (k === "a") askCurrent();
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goSkip, toggleCurrentSaved, askCurrent]);

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
  // Swipe right = read (→), swipe left = skip (←).
  const endDrag = () => {
    const d = drag.current;
    drag.current = null;
    if (d?.axis === "x") {
      if (dragX >= SWIPE_THRESHOLD) goNext();
      else if (dragX <= -SWIPE_THRESHOLD) goSkip();
    }
    setDragX(0);
  };

  const position = Math.min(index + 1, total);
  const filterBar = (
    <FilterBar
      topic={topic}
      onTopic={onTopic}
      topics={topics.data ?? []}
      uncategorisedCount={uncategorised.data ?? 0}
      total={total}
      position={position}
      hasPrev={index > 0}
      onPrev={goPrev}
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
    const item = current;
    const remaining = total - index - 1;
    body = !item ? (
      <ReaderSkeleton />
    ) : (
      <div className="flex h-full flex-col">
        <div className="relative min-h-0 flex-1 lg:max-h-[820px]">
          {/* The stack: the next cards peek out under this one. */}
          {remaining > 0 && (
            <div
              aria-hidden
              className="absolute inset-0 z-[2] translate-y-3 scale-[0.985] rounded-[18px] border border-border bg-surface opacity-75"
            />
          )}
          {remaining > 1 && (
            <div
              aria-hidden
              className="absolute inset-0 z-[1] translate-y-6 scale-[0.97] rounded-[18px] border border-border bg-surface opacity-45"
            />
          )}
          <div
            className={cn(
              "relative z-[3] h-full touch-pan-y will-change-transform",
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
            <FeedCard key={item.id} item={item} />
          </div>
        </div>
        <div className="shrink-0 pt-5 sm:pt-[30px]">
          <FeedActions
            saved={!!item.saved_at}
            onSkip={goSkip}
            onSave={toggleCurrentSaved}
            onRead={goNext}
            onAsk={askCurrent}
          />
        </div>
      </div>
    );
  }

  return (
    <FeedFrame>
      <FeedPanel
        total={total}
        topic={topic}
        onTopic={onTopic}
        topics={topics.data ?? []}
        uncategorised={uncategorised.data ?? 0}
        queue={queue}
        index={Math.min(index, queue.length)}
        onJump={setIndex}
      />
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

/** "Catch up" + a gold progress bar + the counter (mockup `.feed-top`), with
 *  back and the bulk actions beside it; on phones, the topic slice below. */
function FilterBar({
  topic,
  onTopic,
  topics,
  uncategorisedCount,
  total,
  position,
  hasPrev,
  onPrev,
  onMarkAll,
  markAllPending,
}: {
  topic: string | null;
  onTopic: (t: string | null) => void;
  topics: TopicChip[];
  uncategorisedCount: number;
  total: number;
  position: number;
  hasPrev: boolean;
  onPrev: () => void;
  onMarkAll: () => void;
  markAllPending: boolean;
}) {
  const select = (slug: string) => onTopic(topic === slug ? null : slug);
  const pct = total ? Math.max(4, (position / total) * 100) : 0;
  return (
    <div className="mb-3 space-y-3 sm:mb-[18px]">
      <div className="flex items-center gap-3.5">
        <h1 className="font-display text-[22px] font-semibold leading-8 tracking-[-0.02em] sm:text-[26px]">
          Catch up
        </h1>
        <div
          className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={position}
          aria-label="Position in the queue"
        >
          <i
            className="block h-full rounded-full bg-signal transition-[width] duration-[400ms] ease-[cubic-bezier(0.2,0,0,1)]"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="whitespace-nowrap font-mono text-[12px] tabular-nums text-fg-subtle">
          {position} / {total}
        </span>
        <div className="flex items-center">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onPrev}
            disabled={!hasPrev}
            aria-label="Back to the previous card"
            title="Back"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Feed actions">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link to="/topics">
                  <Sparkles className="size-3.5" /> Organise topics
                  {uncategorisedCount > 0 && (
                    <span className="ml-auto font-mono text-[11px] text-fg-subtle">
                      {uncategorisedCount}
                    </span>
                  )}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={onMarkAll} disabled={markAllPending}>
                <CheckCheck className="size-3.5" /> Mark all read
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Topic slice chips (single-select) — phones only: from `md` the slice
          lives in the context panel, beside the up-next queue. One scrolling
          row so the many topics don't crush the card. */}
      <div className="no-scrollbar -mx-4 flex items-center gap-1.5 overflow-x-auto px-4 sm:-mx-6 sm:px-6 md:hidden">
        <FilterChip active={topic === null} onClick={() => onTopic(null)}>
          All
        </FilterChip>
        {uncategorisedCount > 0 && (
          <FilterChip active={topic === UNCATEGORISED} onClick={() => select(UNCATEGORISED)}>
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
          ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
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
 *  the two-column card uses the space instead of a narrow centered column.
 *  Height = the viewport minus the shell's chrome and the content padding:
 *  phones lose the 56px header + 62px tabs + py-6 (py-8 from sm); from `md`
 *  there is no chrome above the content, only py-8. */
function FeedFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto h-[calc(100dvh-166px)] max-w-[720px] sm:h-[calc(100dvh-182px)] md:h-[calc(100dvh-64px)] lg:max-w-[1400px]">
      {children}
    </div>
  );
}
