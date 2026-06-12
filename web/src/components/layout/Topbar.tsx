import { useLocation } from "react-router-dom";
import { Plus, Search } from "lucide-react";
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
  const openAdd = useUi((s) => s.openAdd);
  const isMac = navigator.platform.toLowerCase().includes("mac");

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-bg/80 px-6 backdrop-blur">
      <h1 className="text-[15px] font-semibold">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => setPaletteOpen(true)}
          className="flex h-9 w-56 items-center gap-2 rounded-md border border-border bg-surface px-3 text-[13px] text-fg-subtle transition-colors hover:border-border-strong"
        >
          <Search className="size-4" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
            {isMac ? "⌘" : "Ctrl"}K
          </kbd>
        </button>

        <Button onClick={() => openAdd()} size="sm">
          <Plus className="size-4" /> Add source
        </Button>
      </div>
    </header>
  );
}
