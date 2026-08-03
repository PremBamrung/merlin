import {
  keepPreviousData,
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { getInbox, retryFailed, clearFailed } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { toast } from "@/components/ui/toaster";

/**
 * Failed-ingest data (+ header counts). Backed by the digest endpoint, which
 * still returns the pending-review queue too, but the Feed has replaced that
 * surface — only `failed` is consumed now (by the Library's NeedsAttention
 * strip).
 */
export function useInbox(limit = 50) {
  return useQuery({
    queryKey: keys.inbox(),
    queryFn: () => getInbox(limit),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
}

/** Re-enqueue every failed task; tracks the new task ids for live progress. */
export function useRetryFailed() {
  const qc = useQueryClient();
  const addTask = useActiveTasks((s) => s.add);
  return useMutation({
    mutationFn: retryFailed,
    onSuccess: ({ task_ids }) => {
      task_ids.forEach(addTask);
      qc.invalidateQueries({ queryKey: keys.inbox() });
      qc.invalidateQueries({ queryKey: keys.tasks() });
      toast.success(
        task_ids.length
          ? `Retrying ${task_ids.length} item${task_ids.length > 1 ? "s" : ""}…`
          : "Nothing to retry",
      );
    },
    onError: (err: Error) => toast.error("Couldn't retry", { description: err.message }),
  });
}

/** Delete all failed task rows. */
export function useClearFailed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: clearFailed,
    onSuccess: ({ cleared }) => {
      qc.invalidateQueries({ queryKey: keys.inbox() });
      toast.success(`Cleared ${cleared} failed task${cleared === 1 ? "" : "s"}`);
    },
    onError: (err: Error) => toast.error("Couldn't clear", { description: err.message }),
  });
}
