import { RotateCw, Trash2 } from "lucide-react";
import { useInbox, useRetryFailed, useClearFailed } from "@/hooks/useDigest";
import { FailedCard } from "@/components/inbox/FailedCard";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Failed-ingest triage — the useful half of the retired Inbox, which lived on
 * Today until Today was folded into the Library.
 *
 * It sits in the Library's slot beside the live-progress strip, under the
 * page's controls, rather than pinned above every route. The *announcement* of
 * a failure already happens wherever you are: `useTaskStream` fires an error
 * toast the moment one lands. This is the residue you act on afterwards, and
 * hoisting residue above the fold on five routes only bought a layout shove
 * each time one appeared or was cleared.
 *
 * Renders nothing when there's nothing wrong, so `className` carries any
 * spacing — a wrapper would leave a phantom gap the rest of the time.
 */
export function NeedsAttention({ className }: { className?: string }) {
  const q = useInbox();
  const retryFailed = useRetryFailed();
  const clearFailed = useClearFailed();

  const failed = q.data?.failed ?? [];
  if (failed.length === 0) return null;

  return (
    <section className={cn("space-y-3", className)}>
      {/* Wraps as a whole below ~420px: the label and the two buttons need
          ~380px together, and without this the eyebrow breaks mid-phrase and
          sits alongside them at two lines tall. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow whitespace-nowrap text-fail">
          Needs attention · {failed.length}
        </p>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => retryFailed.mutate()}
            disabled={retryFailed.isPending}
          >
            <RotateCw className="size-3.5" /> Retry all
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => clearFailed.mutate()}
            disabled={clearFailed.isPending}
          >
            <Trash2 className="size-3.5" /> Clear failed
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(360px,1fr))]">
        {failed.map((t) => (
          <FailedCard key={t.id} task={t} />
        ))}
      </div>
    </section>
  );
}
