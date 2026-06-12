import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getInbox,
  digestAction,
  retryFailed,
  clearFailed,
  type DigestAction,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { useActiveTasks } from "@/store/tasks";
import { toast } from "@/components/ui/toaster";

/** The Inbox queue: pending review items + failed tasks + header counts. */
export function useInbox(limit = 50) {
  return useQuery({
    queryKey: keys.inbox(),
    queryFn: () => getInbox(limit),
    staleTime: 15_000,
  });
}

/** Record a keep/dismiss decision; the item leaves the queue. */
export function useDigestAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: DigestAction }) =>
      digestAction(id, action),
    onSuccess: (_data, { action }) => {
      qc.invalidateQueries({ queryKey: keys.inbox() });
      toast.success(action === "keep" ? "Kept in library" : "Dismissed");
    },
    onError: (err: Error) => toast.error("Couldn't update", { description: err.message }),
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
