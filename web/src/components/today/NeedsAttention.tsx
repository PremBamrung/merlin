import { RotateCw, Trash2 } from "lucide-react";
import { useInbox, useRetryFailed, useClearFailed } from "@/hooks/useDigest";
import { FailedCard } from "@/components/inbox/FailedCard";
import { Button } from "@/components/ui/button";

/**
 * Failed-ingest triage, surfaced on Today (the useful half of the retired
 * Inbox). Renders nothing when there's nothing wrong, so it stays out of the
 * way until an ingest actually fails.
 */
export function NeedsAttention() {
  const q = useInbox();
  const retryFailed = useRetryFailed();
  const clearFailed = useClearFailed();

  const failed = q.data?.failed ?? [];
  if (failed.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="eyebrow text-accent">Needs attention · {failed.length}</p>
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
