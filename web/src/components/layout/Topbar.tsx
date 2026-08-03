import { useEffect, useRef } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { Wordmark } from "@/components/brand/Wordmark";
import { IngestRing } from "./IngestRing";
import { Button } from "@/components/ui/button";
import { useIngestActivity } from "@/hooks/useTaskProgress";
import { useUnreadCount } from "@/hooks/useFeed";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/**
 * The app's only navigation: a horizontal top bar. It replaced a 240px left
 * sidebar (and its mobile drawer), with ~240px more width for content on every
 * route.
 *
 * There is deliberately no route-title `<h1>`: the nav already says where you
 * are, and the old TITLES map had gone stale (it still listed the retired Inbox
 * and had never learned about Topics).
 *
 * Today used to lead this list. It was a hero, two stat tiles and a grid that
 * was Library page 1 by another name, so `/` now redirects to the Library and
 * the destination is gone — which is also what got the nav back under the
 * widths below.
 *
 * Below `lg` the nav wraps to its own row *under* the brand. Five items need
 * ~275px, the brand ~150 and the right cluster ~340: they only coexist on one
 * line from about 1024px. At 390 the nav would otherwise run straight through
 * the wordmark, and at 768 the last destinations sat *behind* the search field,
 * reachable only by scrolling a nav nobody expects to scroll.
 */
const DESTINATIONS = [
  // Library leads: it's the home page, so the first destination and `/` agree.
  { to: "/library", label: "Library" },
  { to: "/feed", label: "Feed" },
  { to: "/topics", label: "Topics" },
  { to: "/chat", label: "Chat" },
  { to: "/insights", label: "Insights" },
];

export function Topbar({ className }: { className?: string }) {
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const unread = useUnreadCount();
  const { running } = useIngestActivity();
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const markSize = 26;
  const navRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  // At 390 the destinations still don't fit on one line, so the nav row
  // scrolls. Keep the one you're actually on in view — otherwise landing on
  // Insights shows a nav where nothing looks active.
  useEffect(() => {
    navRef.current
      ?.querySelector("[aria-current='page']")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pathname]);

  const ingestLabel = running > 0 ? `${running} ingest${running === 1 ? "" : "s"} running` : undefined;

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border bg-bg/85 px-4 py-2.5 backdrop-blur sm:px-6 lg:flex-nowrap lg:gap-x-5",
        className,
      )}
    >
      {/* The wordmark's hat overflows its line box — hence the top padding, and
          why this row is taller than the 56px bar it replaces. */}
      <Link
        to="/"
        className="flex shrink-0 items-center gap-2 pt-1"
        aria-label={ingestLabel ? `Merlin — home (${ingestLabel})` : "Merlin — home"}
        title={ingestLabel}
      >
        <span className="relative flex items-center justify-center">
          <Mark size={markSize} decorative />
          <IngestRing size={markSize} />
        </span>
        <Wordmark fontSize="1.16rem" />
      </Link>

      <nav
        ref={navRef}
        aria-label="Primary"
        // `scroll-px-2` is what makes the scroll-into-view above land cleanly:
        // without it `inline: "nearest"` stops 1.4px short and clips the pill's
        // trailing edge.
        className="no-scrollbar order-3 -mx-1 flex w-full min-w-0 gap-0.5 scroll-px-2 overflow-x-auto px-1 lg:order-none lg:mx-0 lg:w-auto lg:px-0"
      >
        {DESTINATIONS.map((d) => (
          <NavLink
            key={d.to}
            to={d.to}
            className={({ isActive }) =>
              cn(
                "shrink-0 whitespace-nowrap rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors",
                isActive
                  ? "bg-accent text-accent-fg"
                  : "text-fg-muted hover:bg-surface-2 hover:text-fg",
              )
            }
          >
            {d.label}
          </NavLink>
        ))}
      </nav>

      <div className="ml-auto flex shrink-0 items-center gap-2">
        {/* Gold = what wants you. The unread count is one of exactly four things
            allowed to use it. */}
        {(unread.data ?? 0) > 0 && (
          <NavLink
            to="/feed"
            title="Unread items"
            className="flex items-center gap-1.5 rounded-md px-1.5 py-1 font-mono text-[12px] tabular-nums text-signal transition-colors hover:bg-surface-2"
          >
            <span className="size-1.5 shrink-0 rounded-full bg-signal" />
            {unread.data}
            <span className="sr-only">unread</span>
          </NavLink>
        )}

        {/* Icon, not a field. This used to be a 224px button dressed as a text
            input, which put two things that look like search boxes on the
            Library — where only one of them was real. The palette it opens is
            unchanged; the ⌘K hint moved into the tooltip. */}
        <button
          onClick={() => setPaletteOpen(true)}
          aria-label="Search"
          title={`Search (${isMac ? "⌘" : "Ctrl"}K)`}
          className="flex size-8 items-center justify-center rounded-md border border-border bg-surface text-fg-subtle transition-colors hover:border-border-strong hover:text-fg"
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
