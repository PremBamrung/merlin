import { useSyncExternalStore } from "react";

/** Live `matchMedia` result — re-renders when the query flips. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** The shell's one layout breakpoint: rail + panel from here, tabs below. */
export const DESKTOP = "(min-width: 768px)";
/** Where the context panel opens by default (it collapses below). */
export const PANEL_AUTO_OPEN = "(min-width: 1280px)";
