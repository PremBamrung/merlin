import { Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { IngestRing } from "./IngestRing";
import { useUi } from "@/store/ui";

/**
 * Phone header (mockup `.topbar` < 760px): the hat mark sits top-left on EVERY
 * screen and opens the context panel as a drawer; then the place title, then
 * search + add. Translucent so content scrolls under it.
 *
 * `slotted`: the route owns the title and the trailing actions, portalled into
 * `titleRef`/`actionsRef` via <HeaderTitle>/<HeaderActions> (headerSlot.tsx).
 *
 * The top padding is the status-bar inset: 0 in Safari, the clock's height in
 * the Home Screen web app (status bar style `black-translucent`).
 */
export function MobileHeader({
  title,
  slotted,
  titleRef,
  actionsRef,
}: {
  title: React.ReactNode;
  slotted?: boolean;
  titleRef?: (el: HTMLElement | null) => void;
  actionsRef?: (el: HTMLElement | null) => void;
}) {
  const setDrawerOpen = useUi((s) => s.setDrawerOpen);
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  return (
    <header className="sticky top-0 z-30 flex h-[calc(3.5rem+env(safe-area-inset-top))] shrink-0 items-center gap-0.5 border-b border-border bg-bg/90 pl-[max(0.5rem,env(safe-area-inset-left))] pr-[max(0.5rem,env(safe-area-inset-right))] pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <button
        onClick={() => setDrawerOpen(true)}
        aria-label="Open panel"
        className="grid size-10 shrink-0 place-items-center rounded-[11px] transition-colors active:bg-surface"
      >
        <span className="relative flex items-center justify-center">
          <Mark size={24} decorative />
          <IngestRing size={24} />
        </span>
      </button>
      <h1
        ref={slotted ? titleRef : undefined}
        className="ml-0.5 min-w-0 flex-1 truncate font-display text-[15px] font-semibold leading-5 tracking-[-0.01em]"
      >
        {slotted ? null : title}
      </h1>
      <button
        onClick={() => setPaletteOpen(true)}
        aria-label="Search"
        className="grid size-10 shrink-0 place-items-center rounded-[11px] text-fg-muted active:bg-surface"
      >
        <Search className="size-[19px]" />
      </button>
      {slotted ? (
        <div ref={actionsRef} className="flex shrink-0 items-center gap-0.5" />
      ) : (
        <button
          onClick={() => openAdd()}
          aria-label="Add source"
          className="grid size-10 place-items-center rounded-[11px] text-fg-muted active:bg-surface"
        >
          <Plus className="size-5" />
        </button>
      )}
    </header>
  );
}
