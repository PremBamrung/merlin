import { useCallback } from "react";
import { useLocation, type To } from "react-router-dom";
import { DESKTOP, useMediaQuery } from "@/hooks/useMediaQuery";

/** The query param that opens the item drawer over any route. */
export const ITEM_PARAM = "item";

/** Router state marking a drawer the app opened itself — so closing it can
 *  step back through history instead of stacking another entry. */
export type DrawerState = { drawer?: true };

/**
 * Where "open this item" goes (decision O1): on desktop the slide-over drawer
 * over the current page (`?item=<id>`), keeping you in context; on phones the
 * full-page Reader, which is the better reading surface at that width. Deep
 * links to `/library/:id` keep working everywhere.
 */
export function useItemHref(): (id: string) => { to: To; state?: DrawerState } {
  const desktop = useMediaQuery(DESKTOP);
  const { pathname, search } = useLocation();
  return useCallback(
    (id: string) => {
      if (!desktop) return { to: `/library/${id}` };
      const sp = new URLSearchParams(search);
      sp.set(ITEM_PARAM, id);
      return { to: { pathname, search: `?${sp}` }, state: { drawer: true } };
    },
    [desktop, pathname, search],
  );
}
