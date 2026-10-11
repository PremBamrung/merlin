import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useNavigationType } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Rail } from "./Rail";
import { ContextPanel } from "./ContextPanel";
import { MobileHeader } from "./MobileHeader";
import { BottomTabs } from "./BottomTabs";
import { PanelTargetsContext } from "./panelTargets";
import { placeFor } from "./places";
import { CommandPalette } from "./CommandPalette";
import { AddSourceDialog } from "@/components/ingest/AddSourceDialog";
import { ResummarizeConfirmDialog } from "@/components/ingest/ResummarizeConfirmDialog";
import { TaskStreams } from "./TaskStreams";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";
import { DESKTOP, PANEL_AUTO_OPEN, useMediaQuery } from "@/hooks/useMediaQuery";
import { ROUTE_CHANGE_EVENT, useRouteChange } from "@/hooks/useRouteChange";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/**
 * The chrome around every route (docs/EVERYDAY_AI_PLAN.md § Approved design
 * spec, "Shell"): icon rail | context panel | main on desktop; on phones a
 * header with the hat mark, the main view, and bottom tabs, with the panel as
 * a left drawer. The panel's content comes from the route via <PanelSlot>.
 */
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

  const desktop = useMediaQuery(DESKTOP);
  const autoOpen = useMediaQuery(PANEL_AUTO_OPEN);
  const panelPref = useUi((s) => s.panelPref);
  const setPanelPref = useUi((s) => s.setPanelPref);
  const drawerOpen = useUi((s) => s.drawerOpen);
  const setDrawerOpen = useUi((s) => s.setDrawerOpen);
  const panelOpen = desktop ? (panelPref === null ? autoOpen : panelPref === "open") : drawerOpen;

  const togglePanel = useCallback(() => {
    if (desktop) setPanelPref(panelOpen ? "closed" : "open");
    else setDrawerOpen(!drawerOpen);
  }, [desktop, panelOpen, drawerOpen, setPanelPref, setDrawerOpen]);
  const closePanel = useCallback(() => {
    if (desktop) setPanelPref("closed");
    else setDrawerOpen(false);
  }, [desktop, setPanelPref, setDrawerOpen]);

  // `[` toggles the panel (not while typing).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "[" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
      e.preventDefault();
      togglePanel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [togglePanel]);

  // Every navigation: the drawer has done its job, and anything outside React
  // that animates on route change (motion, view transitions) hears about it.
  useRouteChange((change) => {
    setDrawerOpen(false);
    window.dispatchEvent(new CustomEvent(ROUTE_CHANGE_EVENT, { detail: change }));
  });

  // The panel's two portal targets, registered by callback ref so <PanelSlot>
  // re-renders into them once they exist.
  const [head, setHead] = useState<HTMLElement | null>(null);
  const [body, setBody] = useState<HTMLElement | null>(null);
  const targets = useMemo(() => ({ head, body }), [head, body]);

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
  // padding, no page scroll.
  const isChat = pathname.startsWith("/chat");

  return (
    <TooltipProvider delayDuration={300}>
      <PanelTargetsContext.Provider value={targets}>
        <div
          data-app="merlin"
          className={cn("flex h-dvh overflow-hidden bg-bg text-fg", !desktop && "flex-col")}
        >
          {desktop && <Rail panelOpen={panelOpen} onTogglePanel={togglePanel} />}
          <ContextPanel
            desktop={desktop}
            open={panelOpen}
            onClose={closePanel}
            headRef={setHead}
            bodyRef={setBody}
          />
          {!desktop && <MobileHeader title={placeFor(pathname)?.label ?? "Merlin"} />}
          <main
            ref={mainRef}
            className={cn("min-w-0 flex-1", isChat ? "overflow-hidden" : "overflow-y-auto")}
          >
            {isChat ? (
              <Outlet />
            ) : (
              /* Wide ceiling so 27"/32" displays fill; grids inside use
                 auto-fill columns, reading views cap their own measure. */
              <div className="mx-auto w-full max-w-[3000px] px-4 py-6 sm:px-6 sm:py-8 lg:px-10 2xl:px-14">
                {/* Ingest state deliberately does *not* live here. Anything the
                    shell renders above the outlet shoves every route's content
                    down the moment an ingest starts and back up when it ends.
                    The strips sit in the Library's own slot, below its
                    controls; the ring around the mark and the task toasts are
                    what reach you on the other routes, and neither reflows. */}
                <Outlet />
              </div>
            )}
          </main>
          {!desktop && <BottomTabs />}
        </div>
      </PanelTargetsContext.Provider>
      <CommandPalette />
      <AddSourceDialog />
      <ResummarizeConfirmDialog />
      {/* Headless: the only SSE connection per in-flight ingest. Lives here so
          progress (and the ring around the mark) survives navigation. */}
      <TaskStreams />
    </TooltipProvider>
  );
}
