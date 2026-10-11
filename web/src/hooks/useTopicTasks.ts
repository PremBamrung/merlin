import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useBackfill,
  useProposeTopics,
  useReclassifyAll,
  useReclassifyTopic,
  type TopicItem,
} from "@/hooks/useTopics";
import { useCancelTask } from "@/hooks/useIngest";
import { getTask } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { toast } from "@/components/ui/toaster";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export type TopicTaskKind = "discovery" | "backfill" | "rescan" | "rescan-all";

/**
 * The Topics place's background jobs — find topics, classify the
 * uncategorised, re-scan one topic or everything. One runs at a time; it's
 * polled until it settles, then the lists refresh and a toast says how it
 * ended. Shared by the overview, the proposals queue and the manage list.
 */
export function useTopicTasks() {
  const propose = useProposeTopics();
  const backfill = useBackfill();
  const reclassify = useReclassifyTopic();
  const reclassifyAll = useReclassifyAll();
  const cancel = useCancelTask();
  const qc = useQueryClient();

  const [taskId, setTaskId] = useState<string | null>(null);
  const [kind, setKind] = useState<TopicTaskKind | null>(null);
  // The topic being re-scanned, for the progress/toast copy.
  const [rescanLabel, setRescanLabel] = useState<string | null>(null);
  const task = useQuery({
    queryKey: keys.task(taskId ?? ""),
    queryFn: () => getTask(taskId!),
    enabled: !!taskId,
    refetchInterval: (q) => (TERMINAL.has(q.state.data?.status ?? "") ? false : 1500),
  });
  useEffect(() => {
    const status = task.data?.status;
    if (!status || !TERMINAL.has(status)) return;
    // React to the external task completing: refresh the lists (no setState).
    qc.invalidateQueries({ queryKey: keys.proposals() });
    qc.invalidateQueries({ queryKey: keys.uncategorisedCount() });
    qc.invalidateQueries({ queryKey: keys.topics() });
    qc.invalidateQueries({ queryKey: keys.items() });
    qc.invalidateQueries({ queryKey: keys.feed() });
    const noun =
      kind === "backfill"
        ? "Backfill"
        : kind === "rescan"
          ? "Re-scan"
          : kind === "rescan-all"
            ? "Full re-scan"
            : "Topic discovery";
    const wasCancelled = !!task.data?.result_data?.cancelled;
    if (status === "failed") toast.error(`${noun} failed`);
    else if (wasCancelled) toast.success(`${noun} stopped — kept the work done so far`);
    else toast.success(`${noun} complete`);
  }, [task.data?.status, task.data?.result_data, kind, qc]);

  const running = !!taskId && !TERMINAL.has(task.data?.status ?? "");
  const busy =
    running || propose.isPending || backfill.isPending || reclassify.isPending || reclassifyAll.isPending;
  // Cancel POST returns instantly ("cancelling"), but the task keeps running to
  // its next checkpoint — keep the button in "Stopping…" until it terminates.
  const stopping = cancel.isPending || (cancel.isSuccess && cancel.variables === taskId && running);

  const started = (k: TopicTaskKind) => (r: { task_id: string }) => {
    setKind(k);
    setTaskId(r.task_id);
  };

  return {
    running,
    busy,
    stopping,
    kind,
    progress: task.data?.progress,
    message:
      task.data?.message ||
      (kind === "backfill"
        ? "Classifying uncategorised items…"
        : kind === "rescan"
          ? `Re-scanning ${rescanLabel ?? "topic"}…`
          : kind === "rescan-all"
            ? "Re-scanning your whole library…"
            : "Clustering uncategorised items…"),
    startDiscovery: () => propose.mutate(undefined, { onSuccess: started("discovery") }),
    startBackfill: () => backfill.mutate(undefined, { onSuccess: started("backfill") }),
    startRescanAll: () => reclassifyAll.mutate(undefined, { onSuccess: started("rescan-all") }),
    startRescan: (topic: TopicItem) =>
      reclassify.mutate(topic.id, {
        onSuccess: (r) => {
          setRescanLabel(topic.label);
          started("rescan")(r);
        },
      }),
    cancel: () => taskId && cancel.mutate(taskId),
  };
}

export type TopicTasks = ReturnType<typeof useTopicTasks>;
