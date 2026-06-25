import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle, Ban, X, Loader2 } from "lucide-react";
import { useTaskProgress } from "@/hooks/useTaskProgress";
import { useCancelTask } from "@/hooks/useIngest";
import { StatusDot } from "@/components/common/StatusDot";
import { ingestLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * A single live ingest row, driven by the task-progress SSE stream. Shows which
 * document is being ingested (its title once known, else the submitted URL) on
 * the primary line, and the pipeline state (message + progress) below it.
 *
 * While the task is still running it carries an X button to cancel that one
 * ingest (cooperative: the worker stops at its next progress checkpoint).
 */
export function TaskRow({ taskId }: { taskId: string }) {
  const { task, status, done, failed, cancelled } = useTaskProgress(taskId);
  const cancel = useCancelTask();
  const percent = Math.max(0, Math.min(100, Math.round(task?.progress ?? 0)));
  const label = task ? ingestLabel(task) : "Fetching…";
  const active = !done && !failed && !cancelled;
  // Optimistically reflect the click while we wait for the SSE `cancelled` frame.
  const cancelling = active && (cancel.isPending || cancel.isSuccess);
  const message = failed
    ? (task?.error ?? "Failed")
    : cancelled
      ? "Cancelled"
      : cancelling
        ? "Cancelling…"
        : (task?.message ?? (status === "queued" ? "Queued…" : "Starting…"));
  const itemId = task?.knowledge_item_id;

  return (
    <div className="rounded-[10px] border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2.5">
        {done ? (
          <CheckCircle2 className="size-4 shrink-0 text-success" strokeWidth={1.5} />
        ) : failed ? (
          <AlertTriangle className="size-4 shrink-0 text-accent" strokeWidth={1.5} />
        ) : cancelled ? (
          <Ban className="size-4 shrink-0 text-fg-subtle" strokeWidth={1.5} />
        ) : (
          <StatusDot status={status} pulse />
        )}
        <span className="flex-1 truncate text-[13px] font-medium text-fg">{label}</span>
        {done && itemId ? (
          <Link
            to={`/library/${itemId}`}
            className="shrink-0 text-[12px] font-medium text-accent hover:text-accent-hover"
          >
            Open →
          </Link>
        ) : (
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-subtle">
            {failed ? "FAILED" : cancelled ? "CANCELLED" : `${percent}%`}
          </span>
        )}
        {active && (
          <button
            type="button"
            onClick={() => cancel.mutate(taskId)}
            disabled={cancelling}
            title="Cancel this ingest"
            aria-label="Cancel this ingest"
            className="shrink-0 rounded-md p-1 text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg disabled:opacity-50"
          >
            {cancelling ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <X className="size-3.5" />
            )}
          </button>
        )}
      </div>

      <p
        className={cn(
          "mt-1 truncate pl-[26px] text-[12px]",
          failed ? "text-accent" : "text-fg-muted",
        )}
      >
        {message}
      </p>

      {active && !cancelling && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-300 ease-linear"
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
    </div>
  );
}
