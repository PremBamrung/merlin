import { Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { IngestRing } from "./IngestRing";
import { useUi } from "@/store/ui";

/**
 * Phone header (mockup `.topbar` < 760px): the hat mark sits top-left on EVERY
 * screen and opens the context panel as a drawer; then the place title, then
 * search + add. Translucent so content scrolls under it.
 */
export function MobileHeader({ title }: { title: React.ReactNode }) {
  const setDrawerOpen = useUi((s) => s.setDrawerOpen);
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-0.5 border-b border-border bg-bg/90 px-2 backdrop-blur-md">
      <button
        onClick={() => setDrawerOpen(true)}
        aria-label="Open panel"
        className="grid size-10 place-items-center rounded-[11px] transition-colors active:bg-surface"
      >
        <span className="relative flex items-center justify-center">
          <Mark size={24} decorative />
          <IngestRing size={24} />
        </span>
      </button>
      <h1 className="ml-0.5 min-w-0 flex-1 truncate font-display text-[15px] font-semibold leading-5 tracking-[-0.01em]">
        {title}
      </h1>
      <button
        onClick={() => setPaletteOpen(true)}
        aria-label="Search"
        className="grid size-10 place-items-center rounded-[11px] text-fg-muted active:bg-surface"
      >
        <Search className="size-[19px]" />
      </button>
      <button
        onClick={() => openAdd()}
        aria-label="Add source"
        className="grid size-10 place-items-center rounded-[11px] text-fg-muted active:bg-surface"
      >
        <Plus className="size-5" />
      </button>
    </header>
  );
}
