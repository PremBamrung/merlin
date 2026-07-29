import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { taskStream, type TaskFrame } from "@/lib/api/client";
import type { Task } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { toast } from "@/components/ui/toaster";

export type TaskProgress = {
  task: Task | null;
  status: string;
  done: boolean;
  failed: boolean;
  cancelled: boolean;
};

/**
 * Opens the SSE stream for one task and publishes every frame to the task store.
 * On completion/failure: toasts, invalidates the library, and drops the id from
 * the active-tasks store.
 *
 * **One stream per task, ever** — mounted only by `TaskStreams`
 * (components/layout/TaskStreams.tsx). Readers use `useTaskProgress` below,
 * which is a pure store selector. Until the top-bar ingest ring existed this
 * hook both streamed *and* rendered, which would now mean two connections per
 * task for anything shown in two places.
 */
export function useTaskStream(taskId: string): void {
  const qc = useQueryClient();
  const remove = useActiveTasks((s) => s.remove);
  const setFrame = useActiveTasks((s) => s.setFrame);

  useEffect(() => {
    const ctrl = new AbortController();
    let finished = false;

    // outcome: "ok" (complete) | "failed" | "cancelled" — drives the toast.
    const settle = (
      frame: Extract<TaskFrame, { task: Task }>,
      outcome: "ok" | "failed" | "cancelled",
    ) => {
      setFrame(taskId, { task: frame.task, status: frame.task.status });
      if (finished) return;
      finished = true;
      qc.invalidateQueries({ queryKey: keys.items() });
      qc.invalidateQueries({ queryKey: keys.tasks() });
      if (frame.task.knowledge_item_id) {
        qc.invalidateQueries({ queryKey: keys.item(frame.task.knowledge_item_id) });
      }
      if (outcome === "ok") {
        toast.success(frame.task.message || "Ingest complete");
      } else if (outcome === "cancelled") {
        toast("Ingestion cancelled");
      } else {
        toast.error("Ingest failed", { description: frame.task.error ?? undefined });
      }
      // Give the UI a beat to show the terminal state, then stop tracking.
      // Cancelled rows clear faster — there's nothing to read on them.
      window.setTimeout(() => remove(taskId), outcome === "cancelled" ? 1500 : 4000);
    };

    (async () => {
      try {
        for await (const frame of taskStream(taskId, ctrl.signal)) {
          const f = frame as TaskFrame;
          if (f.type === "progress") {
            setFrame(taskId, { task: f.task, status: f.task.status });
          } else if (f.type === "complete") {
            settle(f, "ok");
          } else if (f.type === "failed") {
            settle(f, "failed");
          } else if (f.type === "cancelled") {
            settle(f, "cancelled");
          } else if (f.type === "error") {
            setFrame(taskId, {
              task: useActiveTasks.getState().frames[taskId]?.task ?? null,
              status: "failed",
            });
          }
        }
      } catch {
        /* aborted on unmount — ignore */
      }
    })();

    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);
}

/** Read one task's latest streamed state. Opens no connection of its own. */
export function useTaskProgress(taskId: string): TaskProgress {
  const frame = useActiveTasks((s) => s.frames[taskId]);
  const status = frame?.status ?? "processing";
  return {
    task: frame?.task ?? null,
    status,
    done: status === "completed",
    failed: status === "failed",
    cancelled: status === "cancelled",
  };
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/**
 * Aggregate ingest activity for the top-bar ring: how many tasks are still
 * running, and their mean progress. Zero running ⇒ nothing to draw.
 */
export function useIngestActivity(): { running: number; percent: number } {
  const frames = useActiveTasks((s) => s.frames);
  const activeIds = useActiveTasks((s) => s.activeIds);

  const ids = activeIds.filter((id) => !TERMINAL.has(frames[id]?.status ?? "queued"));
  if (ids.length === 0) return { running: 0, percent: 0 };

  const total = ids.reduce(
    (sum, id) => sum + Math.max(0, Math.min(100, frames[id]?.task?.progress ?? 0)),
    0,
  );
  return { running: ids.length, percent: total / ids.length };
}
