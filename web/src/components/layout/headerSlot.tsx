import { useContext } from "react";
import { createPortal } from "react-dom";
import { HeaderTargetsContext } from "./headerTargets";

/**
 * A route that renders <HeaderTitle>/<HeaderActions> replaces the phone
 * header's place title and its Add-source button. Chat puts the thread's
 * title, ⋯ and New chat there instead of stacking a second 56px header under
 * the top bar. Renders nothing on desktop (no phone header, no targets).
 */
export function HeaderTitle({ children }: { children: React.ReactNode }) {
  const { title } = useContext(HeaderTargetsContext);
  return title ? createPortal(children, title) : null;
}

export function HeaderActions({ children }: { children: React.ReactNode }) {
  const { actions } = useContext(HeaderTargetsContext);
  return actions ? createPortal(children, actions) : null;
}
