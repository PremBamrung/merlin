import { Outlet, useLocation } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { AddSourceDialog } from "@/components/ingest/AddSourceDialog";
import { ResummarizeConfirmDialog } from "@/components/ingest/ResummarizeConfirmDialog";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { cn } from "@/lib/utils";

/** The chrome around every route: the top nav + the content slot. */
export function AppShell() {
  useKeyboardShortcuts();
  const { pathname } = useLocation();

  // Chat manages its own full-height layout, so it renders flush: no content
  // padding, no page scroll. The topbar stays — it *is* the navigation now, and
  // hiding it on mobile (which the sidebar era did, to reclaim vertical space)
  // would leave the chat route with no way out.
  const isChat = pathname.startsWith("/chat");

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen flex-col overflow-hidden bg-bg text-fg">
        <Topbar />
        <main className={cn("flex-1", isChat ? "overflow-hidden" : "overflow-y-auto")}>
          {isChat ? (
            <Outlet />
          ) : (
            /* Wide ceiling so 27"/32" displays fill; grids inside use auto-fill
               columns, reading views cap their own measure. The sidebar's 240px
               went to the content, not to a narrower measure. */
            <div className="mx-auto w-full max-w-[3000px] px-4 py-6 sm:px-6 sm:py-8 lg:px-10 2xl:px-14">
              <Outlet />
            </div>
          )}
        </main>
      </div>
      <CommandPalette />
      <AddSourceDialog />
      <ResummarizeConfirmDialog />
    </TooltipProvider>
  );
}
