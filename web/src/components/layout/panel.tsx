import { useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { PanelTargetsContext } from "./panelTargets";

/**
 * The context panel's content follows the place, and the place's route owns
 * the state that content needs (the Library's URL filters, the Feed's cursor,
 * the active chat thread). So routes render their panel *in place* —
 * `<PanelSlot>` — and it is portalled into the shell's panel column. Nothing
 * has to be lifted into a store just to be shown beside the page.
 */

export function PanelSlot({
  title,
  sub,
  children,
}: {
  /** Panel header, e.g. "Library". */
  title: ReactNode;
  /** Small mono tally beside the title, e.g. "808 items". */
  sub?: ReactNode;
  children: ReactNode;
}) {
  const { head, body } = useContext(PanelTargetsContext);
  return (
    <>
      {head &&
        createPortal(
          <h2 className="flex min-w-0 flex-1 items-baseline font-display text-[15px] font-semibold leading-5 tracking-[-0.01em]">
            <span className="truncate">{title}</span>
            {sub != null && (
              <small className="ml-2 whitespace-nowrap font-mono text-[11px] font-normal tracking-normal text-fg-subtle">
                {sub}
              </small>
            )}
          </h2>,
          head,
        )}
      {body && createPortal(children, body)}
    </>
  );
}
