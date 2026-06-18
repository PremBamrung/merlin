import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
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
  Search,
  Play,
} from "lucide-react";
import {
  useItem,
  useUpdateItem,
  useDeleteItem,
  useClearSummary,
  useAdjacentItems,
} from "@/hooks/useItems";
import { useResummarize, useRetry } from "@/hooks/useIngest";
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
import { detailRows } from "@/lib/itemDetails";
import { cn } from "@/lib/utils";

const LENGTHS = ["short", "long"] as const;

export default function ReaderRoute() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const q = useItem(id);
  const [resumTask, setResumTask] = useState<string | null>(null);

  if (q.isLoading) return <ReaderSkeleton />;
  if (q.isError)
    return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data)
    return <ErrorState title="Item not found" onRetry={() => navigate("/library")} />;

  return (
    <Reader item={q.data} resumTask={resumTask} setResumTask={setResumTask} />
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

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(item.title ?? "");
  const [confirmDel, setConfirmDel] = useState(false);
  const [lenOpen, setLenOpen] = useState(false);
  const [tab, setTab] = useState<"summary" | "transcript">("summary");

  const { prev, next } = useAdjacentItems(item.id);

  // ←/→ walk to the adjacent library item (suppressed while typing).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable))
        return;
      if (e.key === "ArrowLeft" && prev) {
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

  const topics = (item.topics ?? {}) as Record<string, unknown>;
  const timestamps = (item.timestamps ?? {}) as Record<string, unknown>;
  const rail = Object.keys(topics).length ? topics : timestamps;
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

  return (
    <div className="space-y-6">
      {/* Top bar: back + adjacent-item pager + actions */}
      <div className="flex items-center justify-between gap-3">
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
                    {item.summary_length === l && <Check className="size-3.5 text-accent" />}
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
              <DropdownMenuItem onSelect={() => clear.mutate()} disabled={!item.summary}>
                <Eraser className="size-4" /> Clear summary
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => setConfirmDel(true)}
                className="text-accent focus:text-accent"
              >
                <Trash2 className="size-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Body: a capped reading column + a context rail (thumbnail/details/topics) */}
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Reading column — fills available width (rail bounds it on the right) */}
        <div className="min-w-0">
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
              <h1 className="text-[28px] font-semibold leading-tight tracking-tight">
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

          <Tabs
            value={tab}
            onValueChange={(v) => setTab(v as "summary" | "transcript")}
            className="mt-7"
          >
            <div className="flex items-center justify-between gap-3">
              <TabsList>
                <TabsTrigger value="summary">Summary</TabsTrigger>
                <TabsTrigger value="transcript" disabled={!item.raw_content}>
                  Transcript
                </TabsTrigger>
              </TabsList>
              {tab === "summary" && item.summary && (
                <CopyButton text={item.summary} label="Copy" />
              )}
              {tab === "transcript" && item.raw_content && (
                <CopyButton text={item.raw_content} label="Copy" />
              )}
            </div>

            <TabsContent value="summary" className="pt-6">
              {item.summary ? (
                <Markdown>{item.summary}</Markdown>
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
          </Tabs>
        </div>

        {/* Context rail — thumbnail, details, topics */}
        <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start">
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
            <dl className="space-y-2 rounded-[10px] border border-border bg-surface p-4">
              {detailRows(item).map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between gap-3">
                  <dt className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-fg-subtle">
                    {label}
                  </dt>
                  <dd className="truncate text-right text-[12.5px] text-fg-muted">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
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

/** Transcript tab — searchable, monospace-ish raw content. */
function Transcript({ text }: { text: string }) {
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!filter || !ref.current) return;
    const mark = ref.current.querySelector("mark");
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [filter]);

  if (!text)
    return <p className="text-[14px] text-fg-muted">No transcript available.</p>;

  const lines = text.split("\n");
  const q = filter.trim().toLowerCase();

  return (
    <div className="space-y-3">
      <div className="relative max-w-[70ch]">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Find in transcript…"
          className="pl-9"
        />
      </div>
      <div
        ref={ref}
        className="max-h-[70vh] max-w-[70ch] space-y-2 overflow-y-auto rounded-[10px] border border-border bg-surface p-4 text-[13.5px] leading-relaxed text-fg/85"
      >
        {lines.map((line, i) => {
          if (!line.trim()) return <div key={i} className="h-2" />;
          const hit = q && line.toLowerCase().includes(q);
          return (
            <p key={i} className={cn(hit && "rounded bg-accent-subtle/60")}>
              {hit ? <Highlight text={line} term={q} /> : line}
            </p>
          );
        })}
      </div>
    </div>
  );
}

function Highlight({ text, term }: { text: string; term: string }) {
  const idx = text.toLowerCase().indexOf(term);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-accent/30 text-fg">{text.slice(idx, idx + term.length)}</mark>
      {text.slice(idx + term.length)}
    </>
  );
}
