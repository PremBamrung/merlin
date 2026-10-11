import { useEffect, useRef } from "react";
import { PanelLeftClose, X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The context panel (mockup `.pn`): one `<aside>` whose content follows the
 * place — routes fill it through `<PanelSlot>` (./panel.tsx), so the two
 * target nodes here are registered with the shell via the callback refs.
 *
 * Desktop: a 280px column (300px from 1900px) that collapses to 0; the inner
 * box keeps its width, so the content slides out rather than reflowing.
 * Mobile: the same aside becomes a left drawer over a scrim.
 */
export function ContextPanel({
  desktop,
  open,
  onClose,
  headRef,
  bodyRef,
}: {
  desktop: boolean;
  open: boolean;
  onClose: () => void;
  headRef: (el: HTMLDivElement | null) => void;
  bodyRef: (el: HTMLDivElement | null) => void;
}) {
  const asideRef = useRef<HTMLElement>(null);

  // A closed panel is out of the tab order and the accessibility tree.
  useEffect(() => {
    const el = asideRef.current;
    if (!el) return;
    if (open) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [open]);

  // Esc closes the mobile drawer.
  useEffect(() => {
    if (desktop || !open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [desktop, open, onClose]);

  return (
    <>
      {!desktop && (
        <div
          aria-hidden
          onClick={onClose}
          className={cn(
            "fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px] transition-opacity duration-300",
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        />
      )}
      <aside
        ref={asideRef}
        aria-label="Context panel"
        className={cn(
          "flex min-w-0 flex-col overflow-hidden bg-ui-panel-bg",
          desktop
            ? cn(
                "shrink-0 border-r transition-[width,border-color] duration-[280ms] ease-[cubic-bezier(0.2,0,0,1)]",
                open
                  ? "w-[280px] border-border min-[1900px]:w-[300px]"
                  : "w-0 border-transparent",
              )
            : cn(
                "fixed inset-y-0 left-0 z-50 w-[min(310px,86vw)] border-r border-border-strong transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.2,0,0,1)]",
                // The shadow only while open: parked off-screen, its 84px blur
                // would still bleed into the viewport's left edge.
                open ? "translate-x-0 shadow-[24px_0_60px_rgb(0_0_0/0.5)]" : "-translate-x-[102%]",
              ),
        )}
      >
        <div
          className={cn(
            "flex h-full flex-col",
            desktop ? "w-[280px] min-[1900px]:w-[300px]" : "w-full",
          )}
        >
          <div className="flex h-14 shrink-0 items-center gap-2 pl-[18px] pr-2.5">
            <div ref={headRef} className="flex min-w-0 flex-1" />
            <button
              onClick={onClose}
              aria-label={desktop ? "Hide panel" : "Close panel"}
              title={desktop ? "Hide panel ([)" : "Close"}
              className="grid size-8 place-items-center rounded-md text-fg-subtle transition-colors hover:bg-surface hover:text-fg"
            >
              {desktop ? <PanelLeftClose className="size-[18px]" /> : <X className="size-[18px]" />}
            </button>
          </div>
          <div ref={bodyRef} className="min-h-0 flex-1 overflow-y-auto px-3 pb-4 pt-0.5" />
        </div>
      </aside>
    </>
  );
}
