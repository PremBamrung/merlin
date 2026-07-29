import { useEffect, useRef } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { Wordmark } from "@/components/brand/Wordmark";
import { Button } from "@/components/ui/button";
import { useUnreadCount } from "@/hooks/useFeed";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/**
 * The app's only navigation: a horizontal top bar. It replaced a 240px left
 * sidebar (and its mobile drawer) — same six destinations, in the same order,
 * with ~240px more width for content on every route.
 *
 * There is deliberately no route-title `<h1>`: the nav already says where you
 * are, and the old TITLES map had gone stale (it still listed the retired Inbox
 * and had never learned about Topics).
 *
 * Below `lg` the nav wraps to its own row *under* the brand. Six items need
 * ~330px, the brand ~150 and the right cluster ~340: they only coexist on one
 * line from about 1024px. At 390 the nav would otherwise run straight through
 * the wordmark, and at 768 the last three destinations sat *behind* the search
 * field, reachable only by scrolling a nav nobody expects to scroll.
 */
const DESTINATIONS = [
  { to: "/", label: "Today", end: true },
  { to: "/feed", label: "Feed" },
  { to: "/library", label: "Library" },
  { to: "/topics", label: "Topics" },
  { to: "/chat", label: "Chat" },
  { to: "/insights", label: "Insights" },
];

export function Topbar({ className }: { className?: string }) {
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const unread = useUnreadCount();
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const markSize = 26;
  const navRef = useRef<HTMLElement>(null);
  const { pathname } = useLocation();

  // At 390 six destinations don't fit on one line, so the nav row scrolls. Keep
  // the destination you're actually on in view — otherwise landing on Insights
  // shows a nav where nothing looks active.
  useEffect(() => {
    navRef.current
      ?.querySelector("[aria-current='page']")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pathname]);

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
        aria-label="Merlin — home"
      >
        <Mark size={markSize} decorative />
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
            end={d.end}
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

        {/* Full search field from `md` up, icon-only below it */}
        <button
          onClick={() => setPaletteOpen(true)}
          className="hidden h-8 w-48 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-[13px] text-fg-subtle transition-colors hover:border-border-strong md:flex lg:w-56"
        >
          <Search className="size-4" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded-sm border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
            {isMac ? "⌘" : "Ctrl"}K
          </kbd>
        </button>
        <button
          onClick={() => setPaletteOpen(true)}
          aria-label="Search"
          className="flex size-8 items-center justify-center rounded-md border border-border bg-surface text-fg-subtle transition-colors hover:border-border-strong md:hidden"
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
