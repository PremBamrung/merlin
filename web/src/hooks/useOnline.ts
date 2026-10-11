import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/lib/api/endpoints";

const OK_EVERY = 30_000;
const DOWN_EVERY = 5_000;

function subscribe(onChange: () => void) {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

/**
 * Whether Merlin is reachable: the browser's own online flag, plus a light
 * `/api/health` poll (every 30s; every 5s while it's failing). Off the
 * tailnet or with the NAS asleep, the app keeps what it has cached
 * browsable and pauses sending.
 */
export function useOnline() {
  const browserOnline = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  const q = useQuery({
    queryKey: ["online"],
    queryFn: getHealth,
    retry: 0,
    refetchInterval: (query) => (query.state.status === "error" ? DOWN_EVERY : OK_EVERY),
    refetchIntervalInBackground: false,
  });
  return {
    online: browserOnline && !q.isError,
    lastContact: q.dataUpdatedAt || null,
    checking: q.isFetching,
    retry: () => q.refetch(),
    retryEvery: DOWN_EVERY / 1000,
  };
}
