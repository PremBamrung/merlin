import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { useTaskProgress } from "@/hooks/useTaskProgress";
import { StatusDot } from "@/components/common/StatusDot";
import { cn } from "@/lib/utils";

/**
 * A single live ingest row, driven by the task-progress SSE stream.
 * Shows a status dot, the latest message, and an animated progress bar.
 */
export function TaskRow({ taskId }: { taskId: string }) {
  const { task, status, done, failed } = useTaskProgress(taskId);
  const percent = Math.max(0, Math.min(100, Math.round(task?.progress ?? 0)));
  const message =
    task?.message ??
    (status === "queued" ? "Queued…" : "Starting…");
  const itemId = task?.knowledge_item_id;

  return (
    <div className="rounded-[10px] border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2.5">
        {done ? (
          <CheckCircle2 className="size-4 shrink-0 text-success" strokeWidth={1.5} />
        ) : failed ? (
          <AlertTriangle className="size-4 shrink-0 text-accent" strokeWidth={1.5} />
        ) : (
          <StatusDot status={status} pulse />
        )}
        <span
          className={cn(
            "flex-1 truncate text-[13px]",
            failed ? "text-accent" : "text-fg-muted",
          )}
        >
          {failed ? (task?.error ?? message) : message}
        </span>
        {done && itemId ? (
          <Link
            to={`/library/${itemId}`}
            className="shrink-0 text-[12px] font-medium text-accent hover:text-accent-hover"
          >
            Open →
          </Link>
        ) : (
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-subtle">
            {failed ? "FAILED" : `${percent}%`}
          </span>
        )}
      </div>

      {!failed && !done && (
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
