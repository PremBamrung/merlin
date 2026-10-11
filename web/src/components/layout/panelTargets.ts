import { createContext } from "react";

/** The two nodes in the shell's context panel that <PanelSlot> portals into. */
export type PanelTargets = { head: HTMLElement | null; body: HTMLElement | null };

export const PanelTargetsContext = createContext<PanelTargets>({ head: null, body: null });
