import { useEffect, useLayoutEffect, useRef } from "react";
import { Outlet, useLocation, useNavigationType } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Topbar } from "./Topbar";
import { CommandPalette } from "./CommandPalette";
import { AddSourceDialog } from "@/components/ingest/AddSourceDialog";
import { ResummarizeConfirmDialog } from "@/components/ingest/ResummarizeConfirmDialog";
import { TaskStreams } from "./TaskStreams";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { cn } from "@/lib/utils";

/** The chrome around every route: the top nav + the content slot. */
export function AppShell() {
  useKeyboardShortcuts();
  const { pathname, key } = useLocation();
  const navType = useNavigationType();
  const mainRef = useRef<HTMLElement>(null);
  // Scroll offset per history entry. The scroll container is `main`, not the
  // window, so React Router's own restoration doesn't see it — which is why the
  // Reader used to open ~66px down, with its back link and pager already off
  // screen, carrying over whatever offset the Library grid had left behind.
  const offsets = useRef(new Map<string, number>());

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    const onScroll = () => offsets.current.set(key, el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [key]);

  useLayoutEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    // Forward navigation starts at the top; back/forward returns you to where
    // you were — which is the whole point of coming back to a long grid.
    const target = navType === "POP" ? (offsets.current.get(key) ?? 0) : 0;
    el.scrollTop = target;
    // The list may still be resolving, in which case the container isn't tall
    // enough yet for the offset to take. One retry after paint covers it.
    if (target > 0) {
      const raf = requestAnimationFrame(() => {
        if (mainRef.current) mainRef.current.scrollTop = target;
      });
      return () => cancelAnimationFrame(raf);
    }
  }, [key, navType]);

  // Chat manages its own full-height layout, so it renders flush: no content
  // padding, no page scroll. The topbar stays — it *is* the navigation now, and
  // hiding it on mobile (which the sidebar era did, to reclaim vertical space)
  // would leave the chat route with no way out.
  const isChat = pathname.startsWith("/chat");

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen flex-col overflow-hidden bg-bg text-fg">
        <Topbar />
        <main
          ref={mainRef}
          className={cn("flex-1", isChat ? "overflow-hidden" : "overflow-y-auto")}
        >
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
      {/* Headless: the only SSE connection per in-flight ingest. Lives here so
          progress (and the top-bar ring) survives navigation away from Today. */}
      <TaskStreams />
    </TooltipProvider>
  );
}
