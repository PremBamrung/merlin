import { createContext } from "react";

/**
 * The phone header's two route-owned nodes: the title, and the actions after
 * search. <HeaderTitle>/<HeaderActions> (headerSlot.tsx) portal into them.
 */
export type HeaderTargets = { title: HTMLElement | null; actions: HTMLElement | null };

export const HeaderTargetsContext = createContext<HeaderTargets>({ title: null, actions: null });
