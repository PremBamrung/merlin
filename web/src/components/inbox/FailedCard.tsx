import { AlertTriangle, RotateCw } from "lucide-react";
import type { Task } from "@/lib/api/endpoints";
import { useRetry } from "@/hooks/useIngest";
import { Button } from "@/components/ui/button";
import { ingestLabel, relDate } from "@/lib/format";

/**
 * A failed ingest task: red-edged card with the real backend error. When the
 * task produced a knowledge item, it can be retried in place; otherwise the
 * header "Retry all" re-submits it from the stored URL.
 */
export function FailedCard({ task }: { task: Task }) {
  const itemId = task.knowledge_item_id ?? "";
  const retry = useRetry(itemId);

  return (
    <div className="flex flex-col gap-2 rounded-[10px] border border-accent-border bg-accent-subtle/30 p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow flex items-center gap-1.5 text-accent">
          <AlertTriangle className="size-3.5" strokeWidth={2} /> Failed
        </span>
        <span className="font-mono text-[11px] text-fg-subtle">
          {relDate(task.created_at)}
        </span>
      </div>

      <p className="truncate text-[13px] font-medium text-fg">{ingestLabel(task)}</p>
      {task.message && (
        <p className="truncate text-[12px] text-fg-muted">{task.message}</p>
      )}
      {task.error && (
        <p className="line-clamp-3 rounded-md bg-bg/40 px-2.5 py-1.5 font-mono text-[11px] leading-relaxed text-fg-muted">
          {task.error}
        </p>
      )}

      {itemId && (
        <div className="pt-0.5">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => retry.mutate({})}
            disabled={retry.isPending}
          >
            <RotateCw className="size-3.5" /> Retry
          </Button>
        </div>
      )}
    </div>
  );
}
