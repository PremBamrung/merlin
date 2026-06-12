import { RotateCw, Trash2, CheckCircle2 } from "lucide-react";
import {
  useInbox,
  useRetryFailed,
  useClearFailed,
} from "@/hooks/useDigest";
import { useActiveTasks } from "@/store/tasks";
import { FailedCard } from "@/components/inbox/FailedCard";
import { ReviewCard } from "@/components/inbox/ReviewCard";
import { TaskRow } from "@/components/ingest/TaskRow";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { CardGridSkeleton } from "@/components/common/Skeletons";
import { thousands } from "@/lib/format";

const LIMIT = 50;

export default function InboxRoute() {
  const q = useInbox(LIMIT);
  const retryFailed = useRetryFailed();
  const clearFailed = useClearFailed();
  const activeIds = useActiveTasks((s) => s.activeIds);

  const counts = q.data?.counts;
  const failed = q.data?.failed ?? [];
  const pending = q.data?.pending ?? [];
  const isEmpty =
    !q.isLoading && !q.isError && failed.length === 0 && pending.length === 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold">Inbox</h1>
          <p className="text-[13px] text-fg-muted">The workshop — review what's new.</p>
        </div>
        {counts && (
          <div className="flex items-center gap-3">
            <span className="eyebrow">
              {thousands(counts.pending)} to review · {counts.processing} processing ·{" "}
              <span className={counts.failed > 0 ? "text-accent" : undefined}>
                {counts.failed} failed
              </span>
            </span>
            {counts.failed > 0 && (
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
            )}
          </div>
        )}
      </div>

      {/* Live retries kicked off from here */}
      {activeIds.length > 0 && (
        <section className="space-y-2">
          <p className="eyebrow">Processing · {activeIds.length} active</p>
          {activeIds.map((id) => (
            <TaskRow key={id} taskId={id} />
          ))}
        </section>
      )}

      {q.isLoading ? (
        <CardGridSkeleton count={6} />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : isEmpty ? (
        <EmptyState
          icon={CheckCircle2}
          title="Inbox zero ✓"
          description="Nothing to review and no failures. Everything you've ingested is in the Library."
        />
      ) : (
        <>
          {failed.length > 0 && (
            <section className="space-y-3">
              <p className="eyebrow text-accent">Needs attention · {failed.length}</p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(360px,1fr))]">
                {failed.map((t) => (
                  <FailedCard key={t.id} task={t} />
                ))}
              </div>
            </section>
          )}

          {pending.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="eyebrow">To review</p>
                {counts && counts.pending > pending.length && (
                  <span className="text-[12px] text-fg-subtle">
                    Showing {pending.length} of {thousands(counts.pending)}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(420px,1fr))]">
                {pending.map((item) => (
                  <ReviewCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
