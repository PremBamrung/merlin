import { Outlet } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { AddSourceDialog } from "@/components/ingest/AddSourceDialog";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

/** The chrome around every route: sidebar + sticky topbar + content slot. */
export function AppShell() {
  useKeyboardShortcuts();
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen overflow-hidden bg-bg text-fg">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 overflow-y-auto">
            {/* Wide ceiling so 27"/32" displays fill; grids inside use
                auto-fill columns, reading views cap their own measure. */}
            <div className="mx-auto w-full max-w-[3000px] px-6 py-8 lg:px-10 2xl:px-14">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
      <CommandPalette />
      <AddSourceDialog />
    </TooltipProvider>
  );
}
