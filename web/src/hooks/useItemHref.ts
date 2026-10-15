import { useCallback } from "react";
import { useLocation, type To } from "react-router-dom";
import { DESKTOP, useMediaQuery } from "@/hooks/useMediaQuery";

/** The query param that opens the item drawer over any route. */
export const ITEM_PARAM = "item";

/** Router state marking a drawer the app opened itself — so closing it can
 *  step back through history instead of stacking another entry. */
export type DrawerState = { drawer?: true };

/**
 * Where "open this item" goes. By default the full-page Reader — browsing the
 * Library, Feed or Topics means you came to read, and the Reader has the room
 * (and the details, sections and item chat). `peek` is for places where the
 * item is a reference you glance at without leaving: a chat source, the ⌘K
 * palette. There, on desktop, it opens the slide-over drawer over the current
 * page (`?item=<id>`); on phones it's still the Reader, the better surface at
 * that width. Deep links to `/library/:id` work everywhere.
 */
export function useItemHref({ peek = false }: { peek?: boolean } = {}): (
  id: string,
) => { to: To; state?: DrawerState } {
  const desktop = useMediaQuery(DESKTOP);
  const { pathname, search } = useLocation();
  return useCallback(
    (id: string) => {
      if (!peek || !desktop) return { to: `/library/${id}` };
      const sp = new URLSearchParams(search);
      sp.set(ITEM_PARAM, id);
      return { to: { pathname, search: `?${sp}` }, state: { drawer: true } };
    },
    [peek, desktop, pathname, search],
  );
}
