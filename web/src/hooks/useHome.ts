import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getHome } from "@/lib/api/endpoints";
import { keys } from "@/lib/queryKeys";

/** The home's "since last time" digest. */
export function useHome(since: string) {
  return useQuery({
    queryKey: keys.home(since),
    queryFn: () => getHome(since),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
}
