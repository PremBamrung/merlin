import { Link } from "react-router-dom";
import { Check, RefreshCw, X, ArrowUpRight, ImageOff } from "lucide-react";
import type { ListItem } from "@/lib/api/endpoints";
import { useDigestAction } from "@/hooks/useDigest";
import { useResummarize } from "@/hooks/useIngest";
import { Button } from "@/components/ui/button";
import { relDate, formatDuration, shortText, thumbnailUrl } from "@/lib/format";

/**
 * A pending-review item: glanceable summary + a triage action bar
 * (Keep / Re-summarize / Dismiss). Keep and Dismiss remove it from the queue;
 * the item always stays in the Library.
 */
export function ReviewCard({ item }: { item: ListItem }) {
  const action = useDigestAction();
  const resummarize = useResummarize(item.id);
  const src = thumbnailUrl(item);
  const meta = [item.channel ?? item.author, relDate(item.ingested_at)]
    .filter(Boolean)
    .join(" · ");
  const busy = action.isPending || resummarize.isPending;

  return (
    <div className="flex flex-col overflow-hidden rounded-[10px] border border-border bg-surface">
      <Link to={`/library/${item.id}`} className="group flex gap-3 p-3">
        <div className="relative aspect-video w-32 shrink-0 overflow-hidden rounded-md bg-surface-2">
          {src ? (
            <img src={src} alt="" loading="lazy" className="size-full object-cover" />
          ) : (
            <div className="flex size-full items-center justify-center text-fg-subtle">
              <ImageOff className="size-4" strokeWidth={1.5} />
            </div>
          )}
          {formatDuration(item.duration) && (
            <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1 py-0.5 font-mono text-[10px] text-white">
              {formatDuration(item.duration)}
            </span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="flex items-start gap-1 text-[13px] font-medium leading-snug text-fg">
            <span className="line-clamp-2">{item.title ?? "Untitled"}</span>
            <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100" />
          </p>
          <p className="mt-1 truncate font-mono text-[11px] uppercase tracking-wide text-fg-subtle">
            {meta}
          </p>
          {item.summary && (
            <p className="mt-1 line-clamp-2 text-[12px] leading-snug text-fg-muted">
              {shortText(item.summary, 120)}
            </p>
          )}
        </div>
      </Link>

      <div className="flex items-center gap-1.5 border-t border-border px-3 py-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => action.mutate({ id: item.id, action: "keep" })}
          disabled={busy}
        >
          <Check className="size-3.5" /> Keep
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => resummarize.mutate({})}
          disabled={busy}
        >
          <RefreshCw className="size-3.5" /> Re-summarize
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto text-fg-subtle"
          onClick={() => action.mutate({ id: item.id, action: "dismiss" })}
          disabled={busy}
        >
          <X className="size-3.5" /> Dismiss
        </Button>
      </div>
    </div>
  );
}
