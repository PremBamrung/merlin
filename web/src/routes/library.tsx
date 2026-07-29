import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Search,
  LayoutGrid,
  List as ListIcon,
  ChevronDown,
  X,
  Rows3,
  Star,
  FileText,
  Library as LibraryIcon,
} from "lucide-react";
import { useItems } from "@/hooks/useItems";
import { useTopics, useUncategorisedCount } from "@/hooks/useTopics";
import { useDebounced } from "@/hooks/useDebounced";
import { useUi, type Density } from "@/store/ui";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ItemGrid } from "@/components/items/ItemGrid";
import { CardGridSkeleton } from "@/components/common/Skeletons";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import type { ItemQuery } from "@/lib/api/endpoints";
import { thousands } from "@/lib/format";
import { cn } from "@/lib/utils";

const PER_PAGE = 24;
const SORTS = [
  { value: "relevance", label: "Relevance" },
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "longest", label: "Longest" },
  { value: "title", label: "Title A→Z" },
];
const DENSITIES: Density[] = ["comfortable", "cozy", "compact"];
/** Sentinel slug for items that have no topic assigned (matches the Feed + backend). */
const UNCATEGORISED = "uncategorised";

/** True when focus is in a text field — grid shortcuts are suppressed there. */
function inEditable(el: EventTarget | null): boolean {
  const n = el as HTMLElement | null;
  return (
    !!n &&
    (/^(INPUT|TEXTAREA|SELECT)$/.test(n.tagName) || n.isContentEditable)
  );
}

export default function LibraryRoute() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { view, setView, density, setDensity } = useUi();
  // Index of the card focused via j/k (−1 = none).
  const [focused, setFocused] = useState(-1);

  // URL is the source of truth for filters/sort/page.
  const search = params.get("search") ?? "";
  const sourceType = params.get("source_type") ?? "";
  const sort = params.get("sort") ?? "newest";
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const tags = params.getAll("tags");
  const topics = params.getAll("topics");
  const savedOnly = params.get("saved") === "true";
  const searchTranscripts = params.get("search_transcripts") === "true";

  // Local, debounced search box that writes back to the URL.
  const [searchDraft, setSearchDraft] = useState(search);
  const debouncedSearch = useDebounced(searchDraft, 250);
  useEffect(() => {
    if (debouncedSearch === search) return;
    const next: Record<string, string | undefined> = {
      search: debouncedSearch || undefined,
      page: undefined,
    };
    // Auto-rank by relevance when a query appears, and restore Newest when it's
    // cleared — but never override a sort the user picked explicitly.
    if (debouncedSearch && sort === "newest") next.sort = "relevance";
    else if (!debouncedSearch && sort === "relevance") next.sort = undefined;
    // The transcript toggle is only meaningful while searching — reset on clear.
    if (!debouncedSearch) next.search_transcripts = undefined;
    update(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);
  // Keep the box in sync when the URL changes externally (e.g. back button) —
  // the render-time "adjust state on prop change" pattern, not an effect.
  const [prevSearch, setPrevSearch] = useState(search);
  if (search !== prevSearch) {
    setPrevSearch(search);
    setSearchDraft(search);
  }

  function update(next: Record<string, string | string[] | undefined>) {
    const sp = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      sp.delete(k);
      if (Array.isArray(v)) v.forEach((x) => sp.append(k, x));
      else if (v !== undefined && v !== "") sp.set(k, v);
    }
    setParams(sp, { replace: true });
  }

  const query: ItemQuery = useMemo(
    () => ({
      search: search || undefined,
      source_type: sourceType || undefined,
      sort,
      tags: tags.length ? tags : undefined,
      topics: topics.length ? topics : undefined,
      saved: savedOnly || undefined,
      search_transcripts: searchTranscripts || undefined,
      page,
      per_page: PER_PAGE,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [search, sourceType, sort, page, tags.join(","), topics.join(","), savedOnly, searchTranscripts],
  );

  const q = useItems(query);
  const { data: topicList } = useTopics();
  const { data: uncatCount = 0 } = useUncategorisedCount();
  const total = q.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const sortLabel = SORTS.find((s) => s.value === sort)?.label ?? "Newest";

  // Multi-select topics — toggle a slug in/out of the URL (backend ORs them).
  const toggleTopic = (slug: string) => {
    const next = topics.includes(slug)
      ? topics.filter((s) => s !== slug)
      : [...topics, slug];
    update({ topics: next.length ? next : undefined, page: undefined });
  };

  const hasFilters = !!(search || sourceType || tags.length || topics.length || savedOnly);
  const items = q.data?.items ?? [];

  const goToPage = (p: number) => {
    update({ page: p === 1 ? undefined : String(p) });
    setFocused(-1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Reset keyboard focus whenever the result set changes (render-time pattern,
  // matching the search box above — no effect, no cascading render).
  const resultSig = `${search}|${sourceType}|${sort}|${page}|${tags.join(",")}|${topics.join(",")}|${savedOnly}|${searchTranscripts}`;
  const [prevSig, setPrevSig] = useState(resultSig);
  if (resultSig !== prevSig) {
    setPrevSig(resultSig);
    setFocused(-1);
  }

  // Grid keyboard nav: j/k move, Enter opens, ←/→ page. Suppressed while typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || inEditable(e.target)) return;
      if (e.key === "j") {
        e.preventDefault();
        setFocused((f) => Math.min(f + 1, items.length - 1));
      } else if (e.key === "k") {
        e.preventDefault();
        setFocused((f) => Math.max((f < 0 ? items.length : f) - 1, 0));
      } else if (e.key === "Enter" && focused >= 0 && items[focused]) {
        navigate(`/library/${items[focused].id}`);
      } else if (e.key === "ArrowRight" && page < totalPages) {
        e.preventDefault();
        goToPage(page + 1);
      } else if (e.key === "ArrowLeft" && page > 1) {
        e.preventDefault();
        goToPage(page - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, focused, page, totalPages]);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <h1 className="font-display text-[24px] font-semibold">Library</h1>
        <span className="eyebrow pb-1">{thousands(total)} sources</span>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
          <Input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="Search your library…"
            className="pl-9"
          />
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="sm">
              Sort: {sortLabel} <ChevronDown className="size-3.5" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {SORTS.map((s) => (
              <DropdownMenuItem
                key={s.value}
                onSelect={() => update({ sort: s.value, page: undefined })}
                className={cn(sort === s.value && "text-accent-lit")}
              >
                {s.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="flex overflow-hidden rounded-md border border-border">
          <button
            onClick={() => setView("grid")}
            className={cn(
              "flex size-8 items-center justify-center transition-colors",
              view === "grid" ? "bg-surface-2 text-fg" : "text-fg-subtle hover:text-fg",
            )}
            aria-label="Grid view"
          >
            <LayoutGrid className="size-4" />
          </button>
          <button
            onClick={() => setView("list")}
            className={cn(
              "flex size-8 items-center justify-center border-l border-border transition-colors",
              view === "list" ? "bg-surface-2 text-fg" : "text-fg-subtle hover:text-fg",
            )}
            aria-label="List view"
          >
            <ListIcon className="size-4" />
          </button>
        </div>

        {view === "grid" && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary" size="sm" className="capitalize">
                <Rows3 className="size-3.5" /> {density}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {DENSITIES.map((d) => (
                <DropdownMenuItem
                  key={d}
                  onSelect={() => setDensity(d)}
                  className={cn("capitalize", density === d && "text-accent-lit")}
                >
                  {d}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Topic filter chips (multi-select) */}
      {((topicList && topicList.length > 0) || uncatCount > 0) && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Chip
            active={!topics.length}
            onClick={() => update({ topics: undefined, page: undefined })}
          >
            All topics
          </Chip>
          {uncatCount > 0 && (
            <Chip
              active={topics.includes(UNCATEGORISED)}
              onClick={() => toggleTopic(UNCATEGORISED)}
            >
              Uncategorised <Count n={uncatCount} />
            </Chip>
          )}
          {topicList?.map((t) => (
            <Chip
              key={t.slug}
              active={topics.includes(t.slug)}
              onClick={() => toggleTopic(t.slug)}
            >
              {t.label} <Count n={t.count} />
            </Chip>
          ))}
        </div>
      )}

      {/* Source-type chips + active tag filters */}
      <div className="flex flex-wrap items-center gap-2">
        <Chip active={!sourceType} onClick={() => update({ source_type: undefined, page: undefined })}>
          All
        </Chip>
        <Chip
          active={sourceType === "youtube"}
          onClick={() => update({ source_type: "youtube", page: undefined })}
        >
          YouTube
        </Chip>
        <button
          onClick={() =>
            update({ saved: savedOnly ? undefined : "true", page: undefined })
          }
          aria-pressed={savedOnly}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
            savedOnly
              ? "border-signal/50 bg-signal/12 text-signal"
              : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
          )}
        >
          <Star className={cn("size-3.5", savedOnly && "fill-signal")} /> Saved
        </button>
        {search && (
          <button
            onClick={() =>
              update({
                search_transcripts: searchTranscripts ? undefined : "true",
                page: undefined,
              })
            }
            aria-pressed={searchTranscripts}
            title="Also match words spoken inside the video transcript"
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
              searchTranscripts
                ? "border-accent-border bg-accent-subtle text-accent-lit"
                : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
            )}
          >
            <FileText className="size-3.5" /> Search transcripts
          </button>
        )}
        {tags.map((t) => (
          <button
            key={t}
            onClick={() =>
              update({ tags: tags.filter((x) => x !== t), page: undefined })
            }
            className="inline-flex items-center gap-1 rounded-full border border-accent-border bg-accent-subtle px-2.5 py-1 font-mono text-[11px] text-accent-lit"
          >
            #{t} <X className="size-3" />
          </button>
        ))}
        {hasFilters && (
          <button
            onClick={() => setParams({}, { replace: true })}
            className="text-[12px] text-fg-subtle underline-offset-2 hover:text-fg hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Body */}
      {q.isLoading ? (
        <CardGridSkeleton count={12} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : total === 0 ? (
        hasFilters ? (
          <EmptyState
            icon={Search}
            title="No matches"
            description="Nothing fits these filters. Try clearing them or searching for something else."
            action={
              <Button variant="secondary" size="sm" onClick={() => setParams({}, { replace: true })}>
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={LibraryIcon}
            title="Your library is empty"
            description="Add a YouTube link and Merlin will transcribe and summarize it."
            action={
              <Button size="sm" onClick={() => useUi.getState().openAdd()}>
                Add your first source
              </Button>
            }
          />
        )
      ) : (
        <>
          <ItemGrid
            items={items}
            density={density}
            view={view}
            highlight={search}
            focusedId={focused >= 0 ? items[focused]?.id : undefined}
          />
          {totalPages > 1 && (
            <Pager page={page} totalPages={totalPages} onPage={goToPage} />
          )}
        </>
      )}
    </div>
  );
}

function Chip({
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
        "rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
        active
          ? "border-accent-border bg-accent-subtle text-fg"
          : "border-border text-fg-muted hover:border-border-strong hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

/** Small tabular count badge shown inside a filter chip. */
function Count({ n }: { n: number }) {
  return (
    <span className="ml-1 font-mono text-[11px] tabular-nums text-fg-subtle">
      {thousands(n)}
    </span>
  );
}

/** Compact numbered pager with ellipses. */
function Pager({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
}) {
  const pages: (number | "…")[] = [];
  const push = (p: number) => pages.push(p);
  push(1);
  const lo = Math.max(2, page - 1);
  const hi = Math.min(totalPages - 1, page + 1);
  if (lo > 2) pages.push("…");
  for (let p = lo; p <= hi; p++) push(p);
  if (hi < totalPages - 1) pages.push("…");
  if (totalPages > 1) push(totalPages);

  return (
    <div className="flex items-center justify-center gap-1 pt-2">
      <Button
        variant="ghost"
        size="icon-sm"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
        aria-label="Previous page"
      >
        ‹
      </Button>
      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`e${i}`} className="px-1.5 text-fg-subtle">
            …
          </span>
        ) : (
          <button
            key={p}
            onClick={() => onPage(p)}
            className={cn(
              "flex h-8 min-w-8 items-center justify-center rounded-md px-2 font-mono text-[12px] tabular-nums transition-colors",
              p === page
                ? "bg-accent-subtle text-fg"
                : "text-fg-muted hover:bg-surface-2 hover:text-fg",
            )}
          >
            {p}
          </button>
        ),
      )}
      <Button
        variant="ghost"
        size="icon-sm"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
        aria-label="Next page"
      >
        ›
      </Button>
    </div>
  );
}
