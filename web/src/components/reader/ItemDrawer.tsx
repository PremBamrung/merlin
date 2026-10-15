import { useLayoutEffect, useRef, useState } from "react";
import { playMorph } from "@/lib/motion";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronRight, ExternalLink, MessageSquare, PanelRight, Play, X } from "lucide-react";
import { SaveStar } from "@/components/common/SaveStar";
import { useItem } from "@/hooks/useItems";
import { useToggleSaved } from "@/hooks/useFeed";
import { ITEM_PARAM, type DrawerState } from "@/hooks/useItemHref";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Markdown } from "@/components/common/Markdown";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { Transcript } from "@/components/reader/Transcript";
import { DetailsList } from "@/components/reader/DetailsList";
import type { Item } from "@/lib/api/endpoints";
import { compactNumber, formatDuration, relDate, thumbnailUrl, youtubeUrl } from "@/lib/format";
import { normalizeSummary } from "@/lib/summary";
import { cn } from "@/lib/utils";

/**
 * The slide-over quick look (docs/EVERYDAY_AI_PLAN.md § Open an item; mockup
 * `.drawer`): opened by `?item=<id>` over whatever page you're on — a chat
 * source or the ⌘K palette (see `useItemHref({ peek })`) — so checking a
 * reference never loses your place. Browsing (Library, Feed, Topics) opens the
 * full Reader instead. Esc, the scrim, the ✕ or Back close it. The full Reader
 * is one click away for editing (tags, topics, re-summarise) and item chat.
 */
export function ItemDrawer() {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const id = params.get(ITEM_PARAM);

  // Keep the last id while the sheet animates out, so it doesn't empty first.
  const [shown, setShown] = useState(id);
  if (id && id !== shown) setShown(id);

  const close = () => {
    if ((location.state as DrawerState | null)?.drawer) {
      navigate(-1);
      return;
    }
    const sp = new URLSearchParams(params);
    sp.delete(ITEM_PARAM);
    navigate({ pathname: location.pathname, search: sp.size ? `?${sp}` : "" }, { replace: true });
  };

  return (
    <DialogPrimitive.Root open={!!id} onOpenChange={(open) => !open && close()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[rgb(12_13_15/0.5)] backdrop-blur-[3px] duration-[240ms] data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-[min(560px,100vw)] flex-col border-l border-border-strong bg-surface shadow-[-24px_0_60px_rgb(0_0_0/0.45)] outline-none duration-[400ms] ease-[cubic-bezier(0.16,1,0.3,1)] data-[state=closed]:animate-out data-[state=closed]:duration-200 data-[state=closed]:slide-out-to-right data-[state=open]:animate-in data-[state=open]:slide-in-from-right min-[2200px]:w-[640px]"
        >
          {shown && <DrawerItem id={shown} />}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function DrawerItem({ id }: { id: string }) {
  const q = useItem(id);
  const item = q.data;
  const eyebrow = item?.topics?.find((t) => t.is_primary)?.label ?? item?.topics?.[0]?.label ?? "Item";

  return (
    <>
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border pl-[18px] pr-3">
        <DialogPrimitive.Title className="eyebrow min-w-0 flex-1 truncate">
          {q.isLoading ? "Loading…" : eyebrow}
        </DialogPrimitive.Title>
        <Button variant="ghost" size="icon-sm" asChild title="Open the full reader">
          <Link to={`/library/${id}`} aria-label="Open the full reader">
            <PanelRight className="size-[17px]" />
          </Link>
        </Button>
        <DialogPrimitive.Close asChild>
          <Button variant="ghost" size="icon-sm" aria-label="Close" title="Close (Esc)">
            <X className="size-[18px]" />
          </Button>
        </DialogPrimitive.Close>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-[22px] pb-8 pt-5">
        {q.isLoading ? (
          <div className="space-y-4">
            <Skeleton className="aspect-video w-full rounded-xl" />
            <Skeleton className="h-7 w-4/5" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : q.isError || !item ? (
          <ErrorState error={q.error ?? "Item not found."} onRetry={() => q.refetch()} />
        ) : (
          <DrawerBody item={item} />
        )}
      </div>
    </>
  );
}

function DrawerBody({ item }: { item: Item }) {
  const toggleSaved = useToggleSaved();
  // Joy — open item: the thumbnail you clicked flies into this hero; the
  // rest of the drawer fades in behind it.
  const [morphed, setMorphed] = useState(false);
  const heroRef = useRef<HTMLImageElement>(null);
  useLayoutEffect(() => {
    if (playMorph(heroRef.current)) setMorphed(true);
  }, []);
  // Local mirror so the ★ answers at once; re-synced when the server's value
  // moves (render-time "adjust state on prop change", not an effect).
  const [saved, setSaved] = useState(!!item.saved_at);
  const [prevSaved, setPrevSaved] = useState(item.saved_at);
  if (item.saved_at !== prevSaved) {
    setPrevSaved(item.saved_at);
    setSaved(!!item.saved_at);
  }
  const thumb = thumbnailUrl(item);
  const watch = item.source_type === "youtube" ? youtubeUrl(item.source_id) : null;
  const duration = formatDuration(item.duration);
  const meta = [
    item.channel ?? item.author,
    relDate(item.published_at ?? item.ingested_at),
    duration,
    item.views ? `${compactNumber(item.views)} views` : null,
  ].filter(Boolean);

  return (
    <>
      {thumb && (
        <a
          href={watch ?? thumb}
          target="_blank"
          rel="noreferrer"
          className="group relative block aspect-video overflow-hidden rounded-xl bg-surface-2"
        >
          <img ref={heroRef} src={thumb} alt="" className="size-full object-cover" />
          {watch && (
            <span className="absolute inset-0 grid place-items-center">
              <span className="grid size-[58px] place-items-center rounded-full border border-white/20 bg-black/55 text-white backdrop-blur-sm transition-transform group-hover:scale-105">
                <Play className="size-[22px] translate-x-px fill-white" />
              </span>
            </span>
          )}
          {duration && (
            <span className="absolute bottom-2 right-2 rounded bg-black/75 px-1.5 py-0.5 font-mono text-[11px] text-white">
              {duration}
            </span>
          )}
        </a>
      )}
      <div className={cn(morphed && "m-drawer-fade")}>
        <h2 className="mb-2 mt-[18px] font-display text-[24px] font-semibold leading-[30px] tracking-[-0.02em]">
          {item.title ?? "Untitled"}
        </h2>
        <p className="flex flex-wrap gap-x-3.5 gap-y-1.5 font-mono text-[12px] leading-[18px] text-fg-subtle">
          {meta.map((m, i) => (
            <span key={i}>{m}</span>
          ))}
        </p>
        <div className="mb-1.5 mt-4 flex flex-wrap gap-2">
          {watch && (
            <Button size="sm" asChild>
              <a href={watch} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" /> Watch on YouTube
              </a>
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            aria-pressed={saved}
            onClick={() => {
              setSaved(!saved);
              toggleSaved.mutate({ id: item.id, saved: !saved });
            }}
          >
            <SaveStar saved={saved} className="size-3.5" />
            {saved ? "Saved" : "Save"}
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/library/${item.id}`}>
              <MessageSquare className="size-3.5" /> Ask about this
            </Link>
          </Button>
        </div>

        <details className="group mt-4">
          <summary className="eyebrow flex w-fit cursor-pointer list-none items-center gap-1 rounded-sm transition-colors hover:text-fg [&::-webkit-details-marker]:hidden">
            <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" />
            Details
          </summary>
          <DetailsList item={item} className="mt-3" />
        </details>

        <Tabs defaultValue="summary" className="mt-5">
          <TabsList>
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="transcript" disabled={!item.raw_content}>
              Transcript
            </TabsTrigger>
          </TabsList>
          <TabsContent value="summary" className="pt-5">
            {item.summary ? (
              <Markdown className="[&>:first-child]:mt-0">{normalizeSummary(item.summary)}</Markdown>
            ) : (
              <p className="text-[14px] text-fg-muted">No summary yet.</p>
            )}
          </TabsContent>
          <TabsContent value="transcript" className="pt-5">
            <Transcript text={item.raw_content ?? ""} />
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
