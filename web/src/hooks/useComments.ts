import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getComments, refreshComments, type Comments } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";
import { toast } from "@/components/ui/toaster";

/** An item's stored top comments. Fetched only when the Comments tab is open. */
export function useComments(itemId: string, enabled = true) {
  return useQuery({
    queryKey: keys.comments(itemId),
    queryFn: () => getComments(itemId),
    enabled: enabled && !!itemId,
  });
}

/** Re-fetch the top comments from YouTube; the response replaces the cache.
 *  `silent` (the tab's automatic first fetch) skips the toasts — the tab shows
 *  the outcome inline. */
export function useRefreshComments(itemId: string) {
  const qc = useQueryClient();
  return useMutation<Comments, Error, { silent?: boolean }>({
    mutationFn: () => refreshComments(itemId),
    onSuccess: (data, vars) => {
      qc.setQueryData(keys.comments(itemId), data);
      if (vars?.silent) return;
      toast.success(
        data.comments.length
          ? `Fetched ${data.comments.length} top comments`
          : "No comments on this video",
      );
    },
    onError: (err: Error, vars) => {
      if (vars?.silent) return;
      toast.error("Couldn't fetch comments", { description: err.message });
    },
  });
}
