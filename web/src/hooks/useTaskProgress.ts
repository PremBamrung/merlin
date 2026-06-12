import { useEffect, useRef, useState } from "react";
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
};

/**
 * Streams a single task's progress via SSE (`/api/tasks/{id}/stream`).
 * On completion/failure: toasts, invalidates the library, and drops the id
 * from the active-tasks store so the Today panel stops tracking it.
 */
export function useTaskProgress(taskId: string): TaskProgress {
  const qc = useQueryClient();
  const remove = useActiveTasks((s) => s.remove);
  const [task, setTask] = useState<Task | null>(null);
  const [status, setStatus] = useState("processing");
  const finished = useRef(false);

  useEffect(() => {
    const ctrl = new AbortController();
    finished.current = false;

    const settle = (frame: Extract<TaskFrame, { task: Task }>, ok: boolean) => {
      setTask(frame.task);
      setStatus(frame.task.status);
      if (finished.current) return;
      finished.current = true;
      qc.invalidateQueries({ queryKey: keys.items() });
      qc.invalidateQueries({ queryKey: keys.tasks() });
      if (frame.task.knowledge_item_id) {
        qc.invalidateQueries({ queryKey: keys.item(frame.task.knowledge_item_id) });
      }
      const title = frame.task.message || (ok ? "Ingest complete" : "Ingest failed");
      if (ok) toast.success(title);
      else toast.error("Ingest failed", { description: frame.task.error ?? undefined });
      // Give the UI a beat to show the terminal state, then stop tracking.
      window.setTimeout(() => remove(taskId), 4000);
    };

    (async () => {
      try {
        for await (const frame of taskStream(taskId, ctrl.signal)) {
          const f = frame as TaskFrame;
          if (f.type === "progress") {
            setTask(f.task);
            setStatus(f.task.status);
          } else if (f.type === "complete") {
            settle(f, true);
          } else if (f.type === "failed") {
            settle(f, false);
          } else if (f.type === "error") {
            setStatus("failed");
          }
        }
      } catch {
        /* aborted on unmount — ignore */
      }
    })();

    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  return {
    task,
    status,
    done: status === "completed",
    failed: status === "failed",
  };
}
