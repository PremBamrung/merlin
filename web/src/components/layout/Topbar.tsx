import { useLocation } from "react-router-dom";
import { Menu, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUi } from "@/store/ui";

const TITLES: Record<string, string> = {
  "": "Today",
  library: "Library",
  inbox: "Inbox",
  chat: "Chat",
  insights: "Insights",
};

function useTitle() {
  const seg = useLocation().pathname.split("/")[1] ?? "";
  return TITLES[seg] ?? "Merlin";
}

export function Topbar() {
  const title = useTitle();
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const setNavOpen = useUi((s) => s.setNavOpen);
  const openAdd = useUi((s) => s.openAdd);
  const isMac = navigator.platform.toLowerCase().includes("mac");

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/80 px-4 backdrop-blur sm:gap-4 sm:px-6">
      <button
        onClick={() => setNavOpen(true)}
        aria-label="Open navigation"
        className="-ml-1 flex size-9 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg md:hidden"
      >
        <Menu className="size-5" />
      </button>

      <h1 className="truncate text-[15px] font-semibold">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        {/* Full search field on desktop, icon-only on mobile */}
        <button
          onClick={() => setPaletteOpen(true)}
          className="hidden h-9 w-56 items-center gap-2 rounded-md border border-border bg-surface px-3 text-[13px] text-fg-subtle transition-colors hover:border-border-strong sm:flex"
        >
          <Search className="size-4" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
            {isMac ? "⌘" : "Ctrl"}K
          </kbd>
        </button>
        <button
          onClick={() => setPaletteOpen(true)}
          aria-label="Search"
          className="flex size-9 items-center justify-center rounded-md border border-border bg-surface text-fg-subtle transition-colors hover:border-border-strong sm:hidden"
        >
          <Search className="size-4" />
        </button>

        <Button onClick={() => openAdd()} size="sm">
          <Plus className="size-4" />
          <span className="hidden sm:inline">Add source</span>
        </Button>
      </div>
    </header>
  );
}
