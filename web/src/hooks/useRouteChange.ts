import { useEffect, useRef } from "react";
import { useLocation, type Location } from "react-router-dom";

/** One navigation: path, query or hash changed (a new history entry). */
export type RouteChange = { from: Location; to: Location };

/** Name of the window event the shell re-broadcasts every route change on, so
 *  code outside React (motion, view transitions) can follow along. */
export const ROUTE_CHANGE_EVENT = "merlin:routechange";

/** Calls `onChange` once per navigation — never on mount. */
export function useRouteChange(onChange: (change: RouteChange) => void) {
  const location = useLocation();
  const prev = useRef<Location | null>(null);
  const cb = useRef(onChange);
  useEffect(() => {
    cb.current = onChange;
  });

  useEffect(() => {
    const from = prev.current;
    prev.current = location;
    if (!from || from.key === location.key) return;
    cb.current({ from, to: location });
  }, [location]);
}
