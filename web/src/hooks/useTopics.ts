import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptProposal,
  createTopic,
  deleteTopic,
  getProposals,
  getTopics,
  getUncategorisedCount,
  patchTopic,
  proposeTopics,
  rejectProposal,
  setItemTopics,
  type TopicItem,
} from "@/lib/api/endpoints";
import type { components } from "@/lib/api/schema";
import { keys } from "@/lib/queryKeys";
import { toast } from "@/components/ui/toaster";

/** The active taxonomy (with per-topic counts) — drives the Feed picker + manage page. */
export function useTopics(status = "active") {
  return useQuery({
    queryKey: [...keys.topics(), status],
    queryFn: () => getTopics(status),
    staleTime: 30_000,
  });
}

/** Count of completed items with no topic yet — drives the "find topics" affordance. */
export function useUncategorisedCount() {
  return useQuery({
    queryKey: keys.uncategorisedCount(),
    queryFn: async () => (await getUncategorisedCount()).count,
    staleTime: 15_000,
  });
}

/** Pending topic proposals awaiting validation on the review page. */
export function useProposals() {
  return useQuery({
    queryKey: keys.proposals(),
    queryFn: getProposals,
    staleTime: 5_000,
  });
}

/** Invalidate everything a taxonomy change can affect. */
function invalidateTopicViews(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: keys.topics() });
  qc.invalidateQueries({ queryKey: keys.uncategorisedCount() });
  qc.invalidateQueries({ queryKey: keys.items() });
  qc.invalidateQueries({ queryKey: keys.feed() }); // matches filter-aware keys
}

export function useCreateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["CreateTopicRequest"]) =>
      createTopic(body),
    onSuccess: () => invalidateTopicViews(qc),
    onError: (e: Error) => toast.error("Couldn't create topic", { description: e.message }),
  });
}

export function usePatchTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: components["schemas"]["PatchTopicRequest"];
    }) => patchTopic(id, body),
    onSuccess: () => invalidateTopicViews(qc),
    onError: (e: Error) => toast.error("Couldn't update topic", { description: e.message }),
  });
}

export function useDeleteTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTopic(id),
    onSuccess: () => {
      invalidateTopicViews(qc);
      toast.success("Topic deleted");
    },
    onError: (e: Error) => toast.error("Couldn't delete topic", { description: e.message }),
  });
}

/** Manual per-item topic assignment (Reader). Invalidates the item + all lists. */
export function useSetItemTopics(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: components["schemas"]["SetItemTopicsRequest"]) =>
      setItemTopics(itemId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.item(itemId) });
      invalidateTopicViews(qc);
    },
    onError: (e: Error) => toast.error("Couldn't set topics", { description: e.message }),
  });
}

/** Trigger the batch proposal pipeline. Returns the background task_id to poll. */
export function useProposeTopics() {
  return useMutation({
    mutationFn: () => proposeTopics(),
    onError: (e: Error) =>
      toast.error("Couldn't start topic discovery", { description: e.message }),
  });
}

export function useAcceptProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body?: components["schemas"]["AcceptProposalRequest"];
    }) => acceptProposal(id, body ?? {}),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: keys.proposals() });
      invalidateTopicViews(qc);
      toast.success(
        `Created “${res.topic.label}” — assigned ${res.assigned} item${res.assigned === 1 ? "" : "s"}`,
      );
    },
    onError: (e: Error) => toast.error("Couldn't accept proposal", { description: e.message }),
  });
}

export function useRejectProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => rejectProposal(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.proposals() }),
    onError: (e: Error) => toast.error("Couldn't reject proposal", { description: e.message }),
  });
}

export type { TopicItem };
