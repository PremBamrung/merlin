import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Command } from "cmdk";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare, Plus, Search, Sparkles } from "lucide-react";
import { searchLibrary, type SearchHit } from "@/lib/api/endpoints";
import { useUi } from "@/store/ui";
import { useDebounced } from "@/hooks/useDebounced";
import { useChatThreads } from "@/hooks/useChatThreads";
import { useItemHref } from "@/hooks/useItemHref";
import { formatDuration, relDate, stripMarkdown, thumbnailUrl } from "@/lib/format";
import { cn } from "@/lib/utils";
import { PLACES } from "./places";
import { Kbd } from "./PanelParts";

/**
 * ⌘K (docs/EVERYDAY_AI_PLAN.md § Search; mockup `.pal`): one box over the
 * whole library — hybrid search (keyword + meaning, `/api/search`), your
 * conversations, and the actions. The first row is always "Ask Merlin about
 * …", so a question typed here is one Enter from an answer (⌘↵ from any row).
 */
export function CommandPalette() {
  const open = useUi((s) => s.paletteOpen);
  const setOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const navigate = useNavigate();
  const itemHref = useItemHref({ peek: true });
  const [query, setQuery] = useState("");
  const debounced = useDebounced(query.trim(), 200);
  const isMac = navigator.platform.toLowerCase().includes("mac");

  // Global ⌘K / Ctrl-K toggle.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUi.getState().paletteOpen);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setOpen]);

  const results = useQuery({
    queryKey: ["palette-search", debounced],
    queryFn: () => searchLibrary(debounced, 8),
    enabled: open && debounced.length >= 2,
    staleTime: 15_000,
  });
  const hits = debounced.length >= 2 ? (results.data?.items ?? []) : [];

  // Conversations: matched by title client-side (the list is small); with no
  // query, the most recent few.
  const threads = useChatThreads().data;
  const convos = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const list = threads ?? [];
    const matched = needle
      ? list.filter((t) => (t.title ?? t.preview ?? "").toLowerCase().includes(needle))
      : list;
    return matched.slice(0, 4);
  }, [threads, query]);

  const go = (fn: () => void) => {
    setOpen(false);
    setQuery("");
    fn();
  };
  const q = query.trim();
  const ask = () => q && go(() => navigate(`/chat?q=${encodeURIComponent(q)}`));
  const terms = useMemo(() => termsOf(debounced), [debounced]);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQuery("");
      }}
      label="Search and commands"
      shouldFilter={false}
      overlayClassName="fixed inset-0 z-50 bg-[rgb(12_13_15/0.62)] backdrop-blur-[3px] data-[state=open]:animate-in data-[state=open]:fade-in-0"
      contentClassName="fixed inset-x-4 top-[11vh] z-50 mx-auto w-auto max-w-[700px] overflow-hidden rounded-2xl border border-border-strong bg-surface-raised shadow-[0_30px_80px_rgb(0_0_0/0.6)] outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-[0.98] data-[state=open]:slide-in-from-bottom-1"
    >
      <DialogPrimitive.Title className="sr-only">Search and commands</DialogPrimitive.Title>
      <div className="flex h-[58px] items-center gap-3 border-b border-border px-4">
        <Search className="size-[19px] shrink-0 text-fg-subtle" />
        <Command.Input
          autoFocus
          value={query}
          onValueChange={setQuery}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              ask();
            }
          }}
          placeholder="Search your library, or ask Merlin…"
          className="h-full min-w-0 flex-1 bg-transparent text-[17px] text-fg outline-none placeholder:text-fg-subtle"
        />
        <span className="hidden whitespace-nowrap rounded-[5px] border border-ui-token-border bg-ui-token-bg px-[7px] py-[5px] font-mono text-[11px] font-medium leading-none text-ui-token-fg sm:inline">
          hybrid · keyword + meaning
        </span>
        <Kbd className="hidden sm:inline">esc</Kbd>
      </div>

      <Command.List className="max-h-[min(62vh,560px)] overflow-y-auto p-1.5">
        {q.length > 0 && (
          <Row value="ask" onSelect={ask}>
            <span className="grid size-10 shrink-0 place-items-center rounded-[10px] border border-ui-tint-border bg-ui-tint-bg text-ui-tint-fg">
              <Sparkles className="size-[19px]" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[14px] font-medium leading-5 text-fg">
                Ask Merlin: “{q}”
              </span>
              <span className="block font-mono text-[11px] leading-4 text-fg-subtle">
                answers from your library, with sources
              </span>
            </span>
            <Kbd>↵</Kbd>
          </Row>
        )}

        {debounced.length >= 2 && (
          <Command.Group
            heading={
              <GroupHead
                left={
                  results.isFetching && !hits.length
                    ? "Library · searching…"
                    : `Library · ${hits.length} ${hits.length === 1 ? "match" : "matches"}`
                }
                right="by relevance"
              />
            }
          >
            {hits.map((hit) => (
              <Row
                key={hit.id}
                value={`item-${hit.id}`}
                onSelect={() =>
                  go(() => {
                    const { to, state } = itemHref(hit.id);
                    navigate(to, { state });
                  })
                }
              >
                <HitRow hit={hit} terms={terms} />
              </Row>
            ))}
          </Command.Group>
        )}

        {convos.length > 0 && (
          <Command.Group heading={<GroupHead left={q ? "Conversations" : "Recent conversations"} />}>
            {convos.map((t) => (
              <Row
                key={t.id}
                value={`thread-${t.id}`}
                onSelect={() => go(() => navigate(`/chat?thread=${t.id}`))}
              >
                <PlainIcon>
                  <MessageSquare className="size-[18px]" />
                </PlainIcon>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium leading-5 text-fg">
                    {t.title || t.preview || "Conversation"}
                  </span>
                  <span className="block font-mono text-[11px] leading-4 text-fg-subtle">
                    {relDate(t.updated_at)} · {t.message_count} messages
                  </span>
                </span>
              </Row>
            ))}
          </Command.Group>
        )}

        <Command.Group heading={<GroupHead left="Actions" />}>
          <Row value="add source" onSelect={() => go(() => openAdd(looksLikeLink(q) ? q : ""))}>
            <PlainIcon>
              <Plus className="size-[18px]" />
            </PlainIcon>
            <span className="min-w-0 flex-1">
              <span className="block text-[14px] font-medium leading-5 text-fg">Add a source…</span>
              <span className="block font-mono text-[11px] leading-4 text-fg-subtle">
                paste a YouTube link
              </span>
            </span>
            <Kbd>A</Kbd>
          </Row>
          {PLACES.filter((p) => !q || p.label.toLowerCase().includes(q.toLowerCase())).map((p) => (
            <Row key={p.to} value={`goto ${p.label}`} onSelect={() => go(() => navigate(p.to))}>
              <PlainIcon>
                <p.icon className="size-[18px]" />
              </PlainIcon>
              <span className="text-[14px] font-medium text-fg">Go to {p.label}</span>
            </Row>
          ))}
        </Command.Group>
      </Command.List>

      <div className="flex flex-wrap items-center gap-4 border-t border-border px-4 py-2.5 text-[12px] text-fg-subtle">
        <span>
          <Kbd>↑</Kbd> <Kbd>↓</Kbd> navigate
        </span>
        <span>
          <Kbd>↵</Kbd> open
        </span>
        <span className="hidden sm:inline">
          <Kbd>{isMac ? "⌘ ↵" : "Ctrl ↵"}</Kbd> ask
        </span>
      </div>
    </Command.Dialog>
  );
}

function Row({
  value,
  onSelect,
  children,
}: {
  value: string;
  onSelect: () => void;
  children: ReactNode;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      // Selected = focus, which is one of gold's four jobs: the inset bar.
      className="flex w-full cursor-pointer items-center gap-3 rounded-[10px] px-2.5 py-2 text-left aria-selected:bg-surface-2 aria-selected:shadow-[inset_2px_0_0_var(--color-signal)]"
    >
      {children}
    </Command.Item>
  );
}

function GroupHead({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <span className="flex justify-between px-2.5 pb-1.5 pt-3 font-mono text-[11px] font-medium uppercase leading-none tracking-[0.08em] text-fg-subtle">
      <span>{left}</span>
      {right && <span>{right}</span>}
    </span>
  );
}

function PlainIcon({ children }: { children: ReactNode }) {
  return (
    <span className="grid size-10 shrink-0 place-items-center rounded-[10px] border border-border-strong bg-surface-2 text-fg-muted">
      {children}
    </span>
  );
}

const MATCH_LABEL: Record<SearchHit["match"], string> = {
  fts: "keyword",
  vector: "meaning",
  both: "keyword + meaning",
};

function HitRow({ hit, terms }: { hit: SearchHit; terms: RegExp | null }) {
  const thumb = thumbnailUrl(hit);
  const topic = hit.topics?.find((t) => t.is_primary)?.label ?? hit.topics?.[0]?.label;
  const meta = [hit.channel ?? hit.author, formatDuration(hit.duration), topic].filter(Boolean);
  return (
    <>
      <span className="aspect-video w-[72px] shrink-0 overflow-hidden rounded-md bg-surface-2">
        {thumb && <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium leading-5 text-fg">
          <Marked text={hit.title ?? "Untitled"} terms={terms} />
        </span>
        <span className="block truncate text-[13px] leading-[18px] text-fg-muted">
          <Marked text={cleanExcerpt(hit.excerpt ?? "")} terms={terms} />
        </span>
        <span className="flex items-center gap-2 font-mono text-[11px] leading-4 text-fg-subtle">
          <span className="min-w-0 truncate">{meta.join(" · ")}</span>
          <span
            className={cn(
              "shrink-0 rounded border px-1 leading-[14px]",
              hit.match === "fts" ? "border-border" : "border-ui-token-border text-ui-token-fg",
            )}
          >
            {MATCH_LABEL[hit.match ?? "fts"]}
          </span>
        </span>
      </span>
    </>
  );
}

/** Excerpts are snippets of the stored markdown; show them as one plain line,
 *  without the summary's own "Overview" label. */
function cleanExcerpt(excerpt: string): string {
  return stripMarkdown(excerpt).replace(
    /^(?:\d+\.\s*)?(?:overview|aperçu(?: général)?|vue d[’']ensemble|résumé de la vidéo)\s*:?\s*/i,
    "",
  );
}

/** One regex of the query's words (≥2 chars) for highlighting matches. */
function termsOf(q: string): RegExp | null {
  const words = q
    .split(/\s+/)
    .map((w) => w.replace(/[^\p{L}\p{N}]/gu, ""))
    .filter((w) => w.length >= 2);
  return words.length ? new RegExp(`(${words.join("|")})`, "giu") : null;
}

function Marked({ text, terms }: { text: string; terms: RegExp | null }) {
  if (!terms) return <>{text}</>;
  return (
    <>
      {text.split(terms).map((part, i) =>
        i % 2 ? (
          <mark key={i} className="rounded-[3px] bg-ui-hl px-px text-fg">
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

function looksLikeLink(s: string): boolean {
  return /^https?:\/\//i.test(s) || /youtu\.?be/i.test(s);
}
