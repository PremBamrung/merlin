import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ingestYouTube, resummarize, retryItem } from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { toast } from "@/components/ui/toaster";

/** Submit a YouTube URL for ingest. Tracks the returned task for live progress. */
export function useIngestYouTube() {
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  return useMutation({
    mutationFn: (body: components["schemas"]["IngestYouTubeRequest"]) =>
      ingestYouTube(body),
    onSuccess: ({ task_id }) => {
      addTask(task_id);
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success("Queued ingest", {
        description: `Tracking task ${task_id.slice(0, 8)}…`,
      });
    },
    onError: (err: Error) => toast.error("Couldn't ingest", { description: err.message }),
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
