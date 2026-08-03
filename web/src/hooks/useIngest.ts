import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { cancelTask, ingestYouTube, resummarize, retryItem } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { useUi } from "@/store/ui";
import { toast } from "@/components/ui/toaster";

/** Submit a YouTube URL for ingest. Tracks the returned task for live progress.
 *
 * If the video is already in the library the server returns `status: "exists"`
 * instead of queueing work — we surface a confirmation prompt (carrying the
 * chosen length/languages) so the user decides whether to redo the summary. */
export function useIngestYouTube() {
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  const openResummarizePrompt = useUi((s) => s.openResummarizePrompt);
  // "Add source" is global but the progress rows live on the Library, so an
  // ingest started from Insights would have nowhere to be watched. The toast
  // carries the way back — no extra chrome on the routes that don't need it.
  const navigate = useNavigate();
  const { pathname } = useLocation();
  return useMutation({
    mutationFn: (body: components["schemas"]["IngestYouTubeRequest"]) =>
      ingestYouTube(body),
    onSuccess: (res, body) => {
      if (res.status === "exists" && res.item_id) {
        openResummarizePrompt({
          itemId: res.item_id,
          title: res.title ?? null,
          summary_length: body.summary_length,
          languages: body.languages ?? ["en", "fr"],
        });
        return;
      }
      if (!res.task_id) return;
      addTask(res.task_id);
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success("Queued ingest", {
        description: `Tracking task ${res.task_id.slice(0, 8)}…`,
        action:
          pathname === "/library"
            ? undefined
            : { label: "View", onClick: () => navigate("/library") },
      });
    },
    onError: (err: Error) => toast.error("Couldn't ingest", { description: err.message }),
  });
}

/** Cancel an in-progress ingest task. The terminal `cancelled` state arrives
 * via the SSE stream (useTaskProgress), which drops it from the active list. */
export function useCancelTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => cancelTask(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.tasks() }),
    onError: (err: Error) =>
      toast.error("Couldn't cancel", { description: err.message }),
  });
}

/** Re-summarize an existing item. */
export function useResummarize(itemId: string) {
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  return useMutation({
    mutationFn: (body: components["schemas"]["ResummarizeRequest"] = {}) =>
      resummarize(itemId, body),
    onSuccess: ({ task_id }) => {
      addTask(task_id);
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success("Re-summarizing…", {
        description: `Tracking task ${task_id.slice(0, 8)}…`,
      });
    },
    onError: (err: Error) =>
      toast.error("Couldn't re-summarize", { description: err.message }),
  });
}

/** Retry a failed item. */
export function useRetry(itemId: string) {
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  return useMutation({
    mutationFn: (body: components["schemas"]["RetryRequest"] = {}) =>
      retryItem(itemId, body),
    onSuccess: ({ task_id }) => {
      addTask(task_id);
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success("Retrying ingest…");
    },
    onError: (err: Error) => toast.error("Couldn't retry", { description: err.message }),
  });
}
