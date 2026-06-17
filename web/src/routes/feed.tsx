import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Inbox as InboxIcon } from "lucide-react";
import { CheckCheck } from "lucide-react";
import {
  useFeedQueue,
  useMarkAllRead,
  useMarkRead,
  useMarkUnread,
  useToggleSaved,
} from "@/hooks/useFeed";
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
import { cn } from "@/lib/utils";

const SWIPE_THRESHOLD = 64; // px of horizontal travel to commit a page-turn
const PREFETCH_AHEAD = 3; // load the next page this many cards before the end

export default function FeedRoute() {
  const q = useFeedQueue();
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
      // Single, self-replacing toast (stable id) — the safety net for an
      // accidental swipe. Undo re-opens the card and walks back to it.
      toast("Marked read", {
        id: "feed-read",
        duration: 4000,
        action: { label: "Undo", onClick: () => undoRead(leaving.id, leavingIdx) },
      });
    }
    if (index < queue.length - 1) setIndex(index + 1);
    else if (hasNextPage) fetchNextPage(); // advance once the page lands
    else setIndex(queue.length); // past the end → caught-up screen
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
  // touch-action: pan-y on the frame lets the summary scroll vertically while
  // we own horizontal drags. We only translate once horizontal intent is clear.
  const drag = useRef<{ x: number; y: number; axis: "" | "x" | "y" } | null>(null);

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
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

  // --- render states ------------------------------------------------------ //
  if (q.isLoading) return <FeedFrame><ReaderSkeleton /></FeedFrame>;
  if (q.isError)
    return (
      <FeedFrame>
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </FeedFrame>
    );

  if (total === 0)
    return (
      <FeedFrame>
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
      </FeedFrame>
    );

  const atEnd = index >= queue.length && !hasNextPage;
  if (atEnd)
    return (
      <FeedFrame>
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
      </FeedFrame>
    );

  const item = queue[Math.min(index, queue.length - 1)];
  if (!item) return <FeedFrame><ReaderSkeleton /></FeedFrame>;

  return (
    <FeedFrame>
      <div className="flex h-full flex-col">
        {/* Header: queue size + bulk action */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="eyebrow">{total} unread</p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirmAll(true)}
            disabled={markAllRead.isPending}
          >
            <CheckCheck className="size-3.5" /> Mark all read
          </Button>
        </div>

        {/* Card stack */}
        <div
          className={cn(
            "min-h-0 flex-1 touch-pan-y select-none will-change-transform",
            // Smooth snap when settled; no transition mid-drag. Honors
            // prefers-reduced-motion via the motion-reduce variant.
            dragX === 0
              ? "transition-transform duration-200 ease-out motion-reduce:transition-none"
              : "transition-none",
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
            onSave={() =>
              toggleSaved.mutate({ id: item.id, saved: !item.saved_at })
            }
            onPrev={goPrev}
            onNext={goNext}
            hasPrev={index > 0}
          />
        </div>
      </div>

      <Dialog open={confirmAll} onOpenChange={setConfirmAll}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Mark all as read?</DialogTitle>
            <DialogDescription>
              All {total} unread {total === 1 ? "summary" : "summaries"} will be
              marked read and cleared from the Feed. They stay in your Library.
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

/** Centered reading frame that fills the viewport height; wide on desktop so
 *  the two-column card uses the space instead of a narrow centered column. */
function FeedFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto h-[calc(100vh-8rem)] max-w-[760px] sm:h-[calc(100vh-9rem)] lg:max-w-[1120px]">
      {children}
    </div>
  );
}
