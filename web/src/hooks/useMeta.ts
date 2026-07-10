import { useQuery } from "@tanstack/react-query";
import {
  getSourceTypes,
  getTags,
  getItems,
  getHealth,
} from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";

export function useSourceTypes() {
  return useQuery({
    queryKey: keys.sourceTypes(),
    queryFn: getSourceTypes,
    staleTime: 30_000,
  });
}

/** Tags with counts. ``unread`` scopes the tally to unread items (Feed Refine). */
export function useTags(unread = false) {
  return useQuery({
    queryKey: [...keys.tags(), unread ? "unread" : "all"],
    queryFn: () => getTags(unread),
    staleTime: 30_000,
  });
}

export function useHealth() {
  return useQuery({ queryKey: keys.health(), queryFn: getHealth, staleTime: 60_000 });
}

/** Total library count — drives the sidebar/topbar badge. */
export function useLibraryCount() {
  return useQuery({
    queryKey: keys.insights("library-count"),
    queryFn: async () => (await getItems({ per_page: 1 })).total,
    staleTime: 30_000,
  });
}
