import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Captions,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  MoreHorizontal,
  Trash2,
  Eraser,
  RotateCw,
  Check,
  Pencil,
  Play,
  Star,
  Plus,
  Sparkles,
  X,
} from "lucide-react";
import {
  useItem,
  useUpdateItem,
  useDeleteItem,
  useClearSummary,
  useAdjacentItems,
  usePrefetchItem,
} from "@/hooks/useItems";
import { useTopics, useSetItemTopics } from "@/hooks/useTopics";
import { useRefetch, useResummarize, useRetry } from "@/hooks/useIngest";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CopyButton } from "@/components/common/CopyButton";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Markdown } from "@/components/common/Markdown";
import { TagInput } from "@/components/items/TagInput";
import { Transcript } from "@/components/reader/Transcript";
import { Comments } from "@/components/reader/Comments";
// Lazy so the Vercel AI SDK loads only when a Reader chat is actually shown.
const ItemChat = lazy(() =>
  import("@/components/chat/ItemChat").then((m) => ({ default: m.ItemChat })),
);
import { TaskRow } from "@/components/ingest/TaskRow";
import { ReaderSkeleton } from "@/components/common/Skeletons";
import { ErrorState } from "@/components/common/ErrorState";
import type { Item } from "@/lib/api/endpoints";
import {
  youtubeUrl,
  tsToSeconds,
  formatDuration,
  thousands,
  readingTime,
  thumbnailUrl,
} from "@/lib/format";
import { DetailsList } from "@/components/reader/DetailsList";
import { normalizeSummary } from "@/lib/summary";
import { vtThumb, vtTitle } from "@/lib/viewTransition";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { LibraryPanel } from "@/components/library/LibraryPanel";

const LENGTHS = ["short", "long"] as const;
type ReaderTab = "summary" | "transcript" | "comments";

export default function ReaderRoute() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const q = useItem(id);
  const [resumTask, setResumTask] = useState<string | null>(null);

  // The Reader belongs to the Library place, so it keeps the Library's panel.
  const panel = <LibraryPanel params={null} />;
  if (q.isLoading) return <>{panel}<ReaderSkeleton /></>;
  if (q.isError)
    return <>{panel}<ErrorState error={q.error} onRetry={() => q.refetch()} /></>;
  if (!q.data)
    return <>{panel}<ErrorState title="Item not found" onRetry={() => navigate("/library")} /></>;

  return (
    <>
      {panel}
      <Reader item={q.data} resumTask={resumTask} setResumTask={setResumTask} />
    </>
  );
}

function Reader({
  item,
  resumTask,
  setResumTask,
}: {
  item: Item;
  resumTask: string | null;
  setResumTask: (id: string | null) => void;
}) {
  const navigate = useNavigate();
  const update = useUpdateItem(item.id);
  const del = useDeleteItem();
  const clear = useClearSummary(item.id);
  const resummarize = useResummarize(item.id);
  const retry = useRetry(item.id);
  const refetch = useRefetch(item.id);

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(item.title ?? "");
  const [confirmDel, setConfirmDel] = useState(false);
  const [lenOpen, setLenOpen] = useState(false);
  const [tab, setTab] = useState<ReaderTab>("summary");

  // Ask = the item chat. One flag drives both layouts: from `lg` it swaps the
  // context rail from Details to the chat; below it, it opens a bottom sheet.
  // The chat mounts on first open (keeps the AI SDK chunk lazy) and then stays
  // mounted — hidden, not unmounted — so toggling never loses the thread.
  const wide = useMediaQuery("(min-width: 1024px)");
  const [askOpen, setAskOpen] = useState(false);
  const [askMounted, setAskMounted] = useState(false);
  const askRef = useRef<HTMLDivElement>(null);
  const openAsk = (open: boolean) => {
    if (open) setAskMounted(true);
    setAskOpen(open);
  };

  // Re-opening should land in the composer (ItemChat only focuses on mount).
  useEffect(() => {
    if (askOpen) askRef.current?.querySelector("textarea")?.focus({ preventScroll: true });
  }, [askOpen]);

  // The sheet is modal on narrow screens: lock page scroll, Esc closes.
  const sheetOpen = askOpen && !wide;
  useEffect(() => {
    if (!sheetOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setAskOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [sheetOpen]);

  const { prev, next } = useAdjacentItems(item.id);
  const prefetch = usePrefetchItem();

  // Warm both neighbours, so ←/→ (and the header arrows) land on content
  // instead of the skeleton. Two requests, once, for the item you're reading.
  useEffect(() => {
    if (prev) prefetch(prev.id);
    if (next) prefetch(next.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prev?.id, next?.id]);

  // ←/→ walk to the adjacent library item, A toggles Ask (as on the Feed).
  // Suppressed while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable))
        return;
      if (new URLSearchParams(window.location.search).has("item")) return;
      if (e.key.toLowerCase() === "a") {
        e.preventDefault();
        setAskMounted(true);
        setAskOpen((o) => !o);
      } else if (e.key === "ArrowLeft" && prev) {
        e.preventDefault();
        navigate(`/library/${prev.id}`);
      } else if (e.key === "ArrowRight" && next) {
        e.preventDefault();
        navigate(`/library/${next.id}`);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next, navigate]);

  const isFailed = item.status === "failed";
  const isYouTube = item.source_type === "youtube";
  const watchUrl = isYouTube ? youtubeUrl(item.source_id) : null;
  const thumb = thumbnailUrl(item);
  const canAsk = !!(item.raw_content || item.summary);

  const sections = (item.sections ?? {}) as Record<string, unknown>;
  const timestamps = (item.timestamps ?? {}) as Record<string, unknown>;
  const rail = Object.keys(sections).length ? sections : timestamps;
  const railEntries = Object.entries(rail);

  const meta = [
    item.source_type.toUpperCase(),
    item.channel ?? item.author,
    formatDuration(item.duration),
    item.detected_language?.toUpperCase(),
    item.word_count ? `${thousands(item.word_count)} words` : null,
    readingTime(item.word_count) || null,
  ].filter(Boolean);

  const saveTitle = () => {
    const t = titleDraft.trim();
    setEditingTitle(false);
    if (t && t !== item.title) update.mutate({ title: t });
  };

  const doResummarize = (length: string) => {
    setLenOpen(false);
    resummarize.mutate(
      { summary_length: length },
      { onSuccess: ({ task_id }) => setResumTask(task_id) },
    );
  };

  const doRetry = () =>
    retry.mutate({}, { onSuccess: ({ task_id }) => setResumTask(task_id) });

  const doRefetch = () =>
    refetch.mutate({}, { onSuccess: ({ task_id }) => setResumTask(task_id) });

  const askPane = (
    <>
      {!wide && (
        <div
          aria-hidden
          onClick={() => setAskOpen(false)}
          className={cn(
            "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity duration-200",
            askOpen ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        />
      )}
      <div
        ref={askRef}
        role={wide ? undefined : "dialog"}
        aria-modal={wide ? undefined : true}
        aria-label="Ask about this item"
        inert={!askOpen}
        className={cn(
          wide
            ? cn("h-[calc(100dvh-11rem)]", !askOpen && "hidden")
            : cn(
                "fixed inset-x-0 bottom-0 z-50 flex h-[85dvh] flex-col rounded-t-[16px] border-t border-border-strong bg-surface pb-[env(safe-area-inset-bottom)] shadow-2xl shadow-black/50",
                "transition-[transform,visibility] duration-300 ease-out",
                askOpen ? "translate-y-0" : "invisible translate-y-full",
              ),
        )}
      >
        {!wide && (
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 pb-2.5 pt-2">
            <div className="flex items-center gap-2">
              <Sparkles className="size-3.5 text-ui-icon" />
              <p className="text-[14px] font-semibold">Ask about this item</p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setAskOpen(false)}
              aria-label="Close"
            >
              <X className="size-4" />
            </Button>
          </div>
        )}
        <Suspense
          fallback={
            <div className="h-full rounded-[10px] border border-border bg-surface" />
          }
        >
          {/* key={item.id} → ephemeral: navigating items resets the chat. */}
          <ItemChat
            key={item.id}
            itemId={item.id}
            className={wide ? "h-full" : "h-auto min-h-0 flex-1 rounded-none border-0"}
          />
        </Suspense>
      </div>
    </>
  );

  return (
    <div className="mx-auto max-w-[1600px] space-y-6">
      {/* Top bar: back + adjacent-item pager + actions.
          `flex-wrap` is load-bearing, not tidiness: at 390px this row wants
          367px in a 358px box, and without it the ⋯ menu is clipped off the
          right edge with no horizontal scroll to reach it — invisible at every
          wider width, which is how it survived this long. */}
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex items-center gap-2">
          <Link
            to="/library"
            className="inline-flex items-center gap-1 text-[13px] text-fg-muted transition-colors hover:text-fg"
          >
            <ChevronLeft className="size-4" /> Library
          </Link>
          {(prev || next) && (
            <div className="ml-1 flex items-center">
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={!prev}
                onClick={() => prev && navigate(`/library/${prev.id}`)}
                aria-label="Previous item"
                title={prev ? `← ${prev.title ?? "Previous"}` : undefined}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={!next}
                onClick={() => next && navigate(`/library/${next.id}`)}
                aria-label="Next item"
                title={next ? `→ ${next.title ?? "Next"}` : undefined}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {canAsk && (
            <Button
              variant={askOpen ? "secondary" : "outline"}
              size="sm"
              onClick={() => openAsk(!askOpen)}
              aria-pressed={askOpen}
              title="Ask about this item (A)"
            >
              <Sparkles className="size-4" /> Ask
            </Button>
          )}
          {watchUrl && (
            <Button variant="outline" size="sm" asChild>
              <a href={watchUrl} target="_blank" rel="noreferrer">
                <ExternalLink className="size-4" /> YouTube
              </a>
            </Button>
          )}
          {isFailed ? (
            <Button size="sm" onClick={doRetry} disabled={retry.isPending}>
              <RotateCw className="size-4" /> Retry
            </Button>
          ) : (
            <Popover open={lenOpen} onOpenChange={setLenOpen}>
              <PopoverTrigger asChild>
                <Button variant="secondary" size="sm" disabled={resummarize.isPending}>
                  <RefreshCw className="size-4" /> Re-summarize
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-48 p-1.5">
                <p className="eyebrow px-2 py-1">Summary length</p>
                {LENGTHS.map((l) => (
                  <button
                    key={l}
                    onClick={() => doResummarize(l)}
                    className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-[13px] capitalize text-fg-muted transition-colors hover:bg-surface hover:text-fg"
                  >
                    {l}
                    {item.summary_length === l && <Check className="size-3.5 text-ui-icon" />}
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="More actions">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {isYouTube && (
                <DropdownMenuItem onSelect={doRefetch} disabled={refetch.isPending}>
                  <Captions className="size-4" /> Re-fetch transcript
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => clear.mutate()} disabled={!item.summary}>
                <Eraser className="size-4" /> Clear summary
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => setConfirmDel(true)}
                className="text-fail focus:text-fail"
              >
                <Trash2 className="size-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Body: header + tabs form the reading column; a context rail holds the
          thumbnail/details/topics. On mobile the rail sits between the header
          and the summary (order-2) so the video is seen before reading.
          `grid-rows-[auto_1fr]` is load-bearing: the rail spans both rows, and
          when it's taller than header + tab content (a short Comments tab, or
          the viewport-tall chat) the spare height must go to row 2 — with
          implicit rows it was split between both, shoving the tabs down. */}
      <div
        className={cn(
          "grid grid-cols-1 gap-x-10 gap-y-6 lg:grid-rows-[auto_1fr]",
          askOpen && wide
            ? "lg:grid-cols-[minmax(0,1fr)_420px]"
            : "lg:grid-cols-[minmax(0,1fr)_340px]",
        )}
      >
        {/* Header — title, meta, tags, progress/failed state */}
        <div className="order-1 min-w-0 lg:order-none lg:col-start-1 lg:row-start-1">
          {editingTitle ? (
            <Input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveTitle();
                if (e.key === "Escape") setEditingTitle(false);
              }}
              onBlur={saveTitle}
              className="text-[22px] font-semibold"
            />
          ) : (
            <button
              onClick={() => {
                setTitleDraft(item.title ?? "");
                setEditingTitle(true);
              }}
              className="group flex items-start gap-2 text-left"
            >
              <h1
                style={{ viewTransitionName: vtTitle(item.id) }}
                className="font-display text-[28px] font-semibold leading-tight tracking-tight"
              >
                {item.title ?? "Untitled"}
              </h1>
              <Pencil className="mt-2.5 size-4 shrink-0 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          )}

          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] uppercase tracking-wide text-fg-subtle">
            {meta.map((m, i) => (
              <span key={i} className="flex items-center gap-2">
                {i > 0 && <span className="text-border-strong">·</span>}
                {m}
              </span>
            ))}
          </p>

          <div className="mt-3">
            <TagInput
              tags={item.tags ?? []}
              onChange={(next) => update.mutate({ tags: next })}
            />
          </div>

          <div className="mt-3">
            <TopicAssign
              itemId={item.id}
              assigned={item.topics ?? []}
            />
          </div>

          {/* Live re-summarize / retry progress */}
          {resumTask && (
            <div className="mt-5">
              <TaskRow taskId={resumTask} />
            </div>
          )}

          {/* Failed state */}
          {isFailed && !resumTask && (
            <div className="mt-5">
              <ErrorState
                title="This item failed to process"
                error={item.error_message ?? "Unknown error."}
                onRetry={doRetry}
              />
            </div>
          )}
        </div>

        {/* Tabs — summary + transcript + top comments */}
        <div className="order-3 min-w-0 lg:order-none lg:col-start-1 lg:row-start-2">
          <Tabs
            value={tab === "comments" && !isYouTube ? "summary" : tab}
            onValueChange={(v) => setTab(v as ReaderTab)}
          >
            <div className="flex items-center justify-between gap-3">
              <TabsList>
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="transcript" disabled={!item.raw_content}>
                  Transcript
                </TabsTrigger>
                {isYouTube && <TabsTrigger value="comments">Comments</TabsTrigger>}
              </TabsList>
              {tab === "summary" && item.summary && (
                <CopyButton text={item.summary} label="Copy" />
              )}
              {tab === "transcript" && item.raw_content && (
                <CopyButton text={item.raw_content} label="Copy" />
              )}
            </div>

            <TabsContent value="summary" className="max-w-[75ch] pt-6">
              {item.summary ? (
                <Markdown>{normalizeSummary(item.summary)}</Markdown>
              ) : (
                <p className="text-[14px] text-fg-muted">
                  No summary yet.{" "}
                  {!isFailed && "Use Re-summarize to generate one."}
                </p>
              )}
            </TabsContent>

            <TabsContent value="transcript" className="pt-6">
              <Transcript text={item.raw_content ?? ""} />
            </TabsContent>

            {isYouTube && (
              <TabsContent value="comments" className="pt-6">
                <Comments
                  itemId={item.id}
                  hasViewerSection={/^##\s*What Viewers Say/im.test(item.summary ?? "")}
                  onResummarize={
                    isFailed ? undefined : () => doResummarize(item.summary_length || "short")
                  }
                  resummarizing={resummarize.isPending || !!resumTask}
                />
              </TabsContent>
            )}
          </Tabs>
        </div>

        {/* Context rail — thumbnail, details, topics. order-2 puts it above the
            summary on mobile; on desktop it's the right column spanning both rows. */}
        <aside className="order-2 lg:order-none lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:sticky lg:top-20 lg:self-start">
          {wide && canAsk && (
            <Tabs
              value={askOpen ? "ask" : "details"}
              onValueChange={(v) => openAsk(v === "ask")}
              className="mb-4"
            >
              <TabsList className="flex w-full">
                <TabsTrigger value="details" className="flex-1 justify-center">
                  Details
                </TabsTrigger>
                <TabsTrigger value="ask" className="flex-1 justify-center">
                  <Sparkles className="size-3.5" /> Ask
                </TabsTrigger>
              </TabsList>
            </Tabs>
          )}

          <div className={cn("space-y-6", askOpen && wide && "hidden")}>
            {thumb && (
              <a
                href={watchUrl ?? thumb}
                target="_blank"
                rel="noreferrer"
                className="group relative block aspect-video overflow-hidden rounded-[10px] border border-border bg-surface-2"
              >
                <img
                  src={thumb}
                  alt={item.title ?? ""}
                  // The other half of the card → Reader morph (see the grid card).
                  style={{ viewTransitionName: vtThumb(item.id) }}
                  className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
                />
                {watchUrl && (
                  <span className="absolute inset-0 flex items-center justify-center bg-black/15 opacity-0 transition-opacity group-hover:opacity-100">
                    <span className="flex size-12 items-center justify-center rounded-full bg-black/65 ring-1 ring-white/20">
                      <Play className="size-5 translate-x-px fill-white text-white" />
                    </span>
                  </span>
                )}
                {formatDuration(item.duration) && (
                  <span className="absolute bottom-2 right-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-white">
                    {formatDuration(item.duration)}
                  </span>
                )}
              </a>
            )}

            <div>
              <p className="eyebrow mb-3">Details</p>
              <DetailsList item={item} />
            </div>

            {railEntries.length > 0 && (
              <div>
                <p className="eyebrow mb-3">On this page</p>
                <ul className="space-y-1.5">
                  {railEntries.map(([topic, stamp]) => {
                    const secs = tsToSeconds(String(stamp));
                    const href =
                      isYouTube && secs !== null
                        ? youtubeUrl(item.source_id, secs)
                        : null;
                    return (
                      <li key={topic}>
                        {href ? (
                          <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-baseline justify-between gap-2 rounded-md px-2 py-1 text-[13px] text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg"
                          >
                            <span className="truncate">{topic}</span>
                            <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-subtle">
                              {String(stamp)}
                            </span>
                          </a>
                        ) : (
                          <span className="block px-2 py-1 text-[13px] text-fg-muted">
                            {topic}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>

          {/* The chat: the rail's Ask pane from `lg`, a bottom sheet below.
              The sheet is portalled to <body> — `main.m-view` has a
              view-transition-name, which makes it a stacking context, so a
              fixed sheet inside it sits under the nav rail and bottom tabs.
              Toggling only hides it, so the thread survives; crossing the
              breakpoint remounts it. */}
          {canAsk && askMounted && (wide ? askPane : createPortal(askPane, document.body))}
        </aside>
      </div>

      {/* Delete confirm */}
      <Dialog open={confirmDel} onOpenChange={setConfirmDel}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete this item?</DialogTitle>
            <DialogDescription>
              “{item.title ?? "Untitled"}” will be permanently removed from your
              library. This can't be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => setConfirmDel(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                del.mutate(item.id, {
                  onSuccess: () => navigate("/library"),
                })
              }
              disabled={del.isPending}
            >
              <Trash2 className="size-4" /> Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Manual topic assignment for a single item. Chips show assigned topics
 *  (primary starred); click a chip to make it primary, the × to remove, and
 *  the ＋ menu to add from the active taxonomy. Writes the full set via
 *  set_item_topics (assigned_by="user", so the classifier won't clobber it). */
function TopicAssign({
  itemId,
  assigned,
}: {
  itemId: string;
  assigned: { slug: string; label: string; is_primary?: boolean }[];
}) {
  const topics = useTopics();
  const setTopics = useSetItemTopics(itemId);
  const slugToId = useMemo(
    () => Object.fromEntries((topics.data ?? []).map((t) => [t.slug, t.id])),
    [topics.data],
  );
  const assignedSlugs = assigned.map((a) => a.slug);
  const primarySlug = assigned.find((a) => a.is_primary)?.slug ?? assignedSlugs[0];

  // Resolve slugs → ids (drops any unresolvable, e.g. an archived topic) and
  // persist the full set with a single primary.
  const commit = (slugs: string[], primary: string | undefined) => {
    const ids = slugs.map((s) => slugToId[s]).filter(Boolean) as string[];
    const primaryId =
      primary && slugToId[primary] ? slugToId[primary] : (ids[0] ?? null);
    setTopics.mutate({ topic_ids: ids, primary_id: primaryId });
  };
  const remove = (slug: string) =>
    commit(
      assignedSlugs.filter((s) => s !== slug),
      primarySlug === slug ? undefined : primarySlug,
    );
  const add = (slug: string) => {
    if (assignedSlugs.includes(slug)) return;
    commit([...assignedSlugs, slug], primarySlug ?? slug);
  };
  const makePrimary = (slug: string) => commit(assignedSlugs, slug);

  const available = (topics.data ?? []).filter(
    (t) => !assignedSlugs.includes(t.slug),
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {assigned.map((a) => (
        <span
          key={a.slug}
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px]",
            a.is_primary
              ? "border-ui-toggle-on-border bg-ui-toggle-on-bg text-ui-toggle-on-fg"
              : "border-border text-fg-muted",
          )}
        >
          <button
            onClick={() => makePrimary(a.slug)}
            title={a.is_primary ? "Primary topic" : "Make primary"}
            className="inline-flex items-center gap-1"
          >
            {a.is_primary && <Star className="size-3 fill-ui-toggle-on-icon stroke-ui-toggle-on-icon" />}
            {a.label}
          </button>
          <button onClick={() => remove(a.slug)} aria-label={`Remove ${a.label}`}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="inline-flex items-center gap-1 rounded-full border border-dashed border-border px-2.5 py-1 text-[11px] text-fg-subtle transition-colors hover:text-fg">
            <Plus className="size-3" /> Topic
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {available.length === 0 ? (
            <DropdownMenuItem disabled>
              {topics.data?.length ? "All topics assigned" : "No topics yet"}
            </DropdownMenuItem>
          ) : (
            available.map((t) => (
              <DropdownMenuItem key={t.id} onSelect={() => add(t.slug)}>
                {t.label}
              </DropdownMenuItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
