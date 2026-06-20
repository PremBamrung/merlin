import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { AddSourceDialog } from "@/components/ingest/AddSourceDialog";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/** The chrome around every route: sidebar + sticky topbar + content slot. */
export function AppShell() {
  useKeyboardShortcuts();
  const navOpen = useUi((s) => s.navOpen);
  const setNavOpen = useUi((s) => s.setNavOpen);
  const { pathname } = useLocation();

  // Chat manages its own full-height layout and (on mobile) its own header, so
  // it renders flush: no content padding, and the global topbar is hidden on
  // mobile to reclaim vertical space (kept on desktop).
  const isChat = pathname.startsWith("/chat");

  // Close the mobile drawer on route change and on Escape.
  useEffect(() => setNavOpen(false), [pathname, setNavOpen]);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setNavOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen, setNavOpen]);

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen overflow-hidden bg-bg text-fg">
        {/* Static sidebar — desktop / tablet only */}
        <Sidebar className="hidden md:flex" />

        {/* Mobile drawer: backdrop + slide-in panel, below `md` only */}
        <div
          className={cn(
            "fixed inset-0 z-50 md:hidden",
            navOpen ? "pointer-events-auto" : "pointer-events-none",
          )}
        >
          <div
            onClick={() => setNavOpen(false)}
            className={cn(
              "absolute inset-0 bg-black/60 transition-opacity duration-200",
              navOpen ? "opacity-100" : "opacity-0",
            )}
          />
          <Sidebar
            onNavigate={() => setNavOpen(false)}
            className={cn(
              "absolute inset-y-0 left-0 bg-surface shadow-xl transition-transform duration-200 ease-out",
              navOpen ? "translate-x-0" : "-translate-x-full",
            )}
          />
        </div>

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar className={cn(isChat && "hidden md:flex")} />
          <main className={cn("flex-1", isChat ? "overflow-hidden" : "overflow-y-auto")}>
            {isChat ? (
              <Outlet />
            ) : (
              /* Wide ceiling so 27"/32" displays fill; grids inside use
                 auto-fill columns, reading views cap their own measure. */
              <div className="mx-auto w-full max-w-[3000px] px-4 py-6 sm:px-6 sm:py-8 lg:px-10 2xl:px-14">
                <Outlet />
              </div>
            )}
          </main>
        </div>
      </div>
      <CommandPalette />
      <AddSourceDialog />
    </TooltipProvider>
  );
}
