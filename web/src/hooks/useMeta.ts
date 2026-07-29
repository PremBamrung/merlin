import { keepPreviousData, useQuery } from "@tanstack/react-query";
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
    placeholderData: keepPreviousData,
  });
}

/** Tags with counts. ``unread`` scopes the tally to unread items (Feed Refine). */
export function useTags(unread = false) {
  return useQuery({
    queryKey: [...keys.tags(), unread ? "unread" : "all"],
    queryFn: () => getTags(unread),
    placeholderData: keepPreviousData,
  });
}

export function useHealth() {
  return useQuery({ queryKey: keys.health(), queryFn: getHealth, staleTime: 60_000 });
}

/** Total library count — drives the Library header tally. */
export function useLibraryCount() {
  return useQuery({
    queryKey: keys.insights("library-count"),
    queryFn: async () => (await getItems({ per_page: 1 })).total,
    placeholderData: keepPreviousData,
  });
}
