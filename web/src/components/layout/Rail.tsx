import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { PanelLeft, Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { IngestRing } from "./IngestRing";
import { PLACES, isCurrent, placeFor } from "./places";
import { useIngestActivity } from "@/hooks/useTaskProgress";
import { useUnreadCount } from "@/hooks/useFeed";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/**
 * The icon rail: the ONLY navigation on desktop (mockup `.rail`). The mark on
 * top carries the ingest ring (and tips its hat on hover); the places sit
 * below it; the bottom holds the global tools (search, add, panel). The Feed's
 * gold count is one of the few things allowed to be gold — it says something
 * wants you, and it pulses and ticks up when new items arrive.
 *
 * "You are here" is ONE pill that glides between places rather than a
 * background that jumps.
 *
 * Settings + avatar from the mockup land with the Settings place (Phase 1).
 */
export function Rail({ panelOpen, onTogglePanel }: { panelOpen: boolean; onTogglePanel: () => void }) {
  const unreadQ = useUnreadCount().data;
  const unread = unreadQ ?? 0;
  const { pathname } = useLocation();
  const { running } = useIngestActivity();
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const ingestLabel = running > 0 ? `${running} ingest${running === 1 ? "" : "s"} running` : undefined;

  // The gliding pill: measured from the current place's tile.
  const items = useRef(new Map<string, HTMLAnchorElement>());
  const [pill, setPill] = useState<{ top: number; height: number } | null>(null);
  const current = placeFor(pathname)?.id;
  useLayoutEffect(() => {
    const el = current ? items.current.get(current) : undefined;
    setPill(el ? { top: el.offsetTop, height: el.offsetHeight } : null);
  }, [current]);

  // Joy — new items: the count pulses gold and ticks when it goes up — not
  // when it first loads.
  const prevUnread = useRef<number | undefined>(undefined);
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    if (unreadQ === undefined) return;
    if (prevUnread.current !== undefined && unreadQ > prevUnread.current) setPulse((n) => n + 1);
    prevUnread.current = unreadQ;
  }, [unreadQ]);

  return (
    <nav
      aria-label="Places"
      className="relative z-20 flex w-[68px] shrink-0 flex-col items-center gap-1 border-r border-border bg-ui-rail-bg py-3"
    >
      <Link
        to="/"
        viewTransition
        className="m-hat-tip mb-2.5 grid size-11 place-items-center rounded-xl transition-colors hover:bg-surface"
        aria-label={ingestLabel ? `Merlin — home (${ingestLabel})` : "Merlin — home"}
        title={ingestLabel}
      >
        <span className="relative flex items-center justify-center">
          <Mark size={26} decorative />
          <IngestRing size={26} />
        </span>
      </Link>

      {pill && (
        <span
          aria-hidden
          className="m-rail-pill pointer-events-none absolute left-[7px] top-0 w-[54px] rounded-[11px] bg-ui-current-bg shadow-[inset_0_0_0_1px_var(--color-ui-current-border),0_1px_2px_rgb(0_0_0/0.35)]"
          style={{ transform: `translateY(${pill.top}px)`, height: pill.height }}
        />
      )}

      {PLACES.map((p) => {
        const on = isCurrent(p, pathname);
        return (
          <NavLink
            key={p.id}
            to={p.to}
            viewTransition
            ref={(el) => {
              if (el) items.current.set(p.id, el);
              else items.current.delete(p.id);
            }}
            aria-current={on ? "page" : undefined}
            className={() =>
              cn(
                "group relative z-[1] flex w-[54px] flex-col items-center gap-1 rounded-[11px] pb-[7px] pt-2 text-[10.5px] font-medium leading-3 transition-colors",
                on ? "text-fg" : "text-fg-subtle hover:bg-surface hover:text-fg",
              )
            }
          >
            <p.icon className={cn("size-5", on && "text-ui-current-fg")} strokeWidth={1.75} />
            {p.label}
            {p.id === "feed" && unread > 0 && (
              <span
                key={pulse}
                className={cn(
                  "absolute right-[5px] top-[3px] h-[17px] min-w-[17px] overflow-hidden rounded-full bg-signal px-1 text-center font-mono text-[10px] font-semibold leading-[17px] text-bg shadow-[0_0_0_2px_var(--color-ui-rail-bg)]",
                  pulse > 0 && "m-pulse",
                )}
                aria-label={`${unread} unread`}
              >
                <span className={cn(pulse > 0 && "m-tick")}>{unread > 99 ? "99+" : unread}</span>
              </span>
            )}
          </NavLink>
        );
      })}

      <div className="flex-1" />

      <RailTool label={`Search (${isMac ? "⌘" : "Ctrl"}K)`} onClick={() => setPaletteOpen(true)}>
        <Search className="size-[18px]" />
      </RailTool>
      <RailTool label="Add source (A)" onClick={() => openAdd()}>
        <Plus className="size-[18px]" />
      </RailTool>
      <RailTool
        label={panelOpen ? "Hide panel ([)" : "Show panel ([)"}
        onClick={onTogglePanel}
        pressed={panelOpen}
      >
        <PanelLeft className="size-[18px]" />
      </RailTool>
    </nav>
  );
}

function RailTool({
  label,
  onClick,
  pressed,
  children,
}: {
  label: string;
  onClick: () => void;
  pressed?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className="grid h-10 w-11 place-items-center rounded-[10px] text-fg-subtle transition-colors hover:bg-surface hover:text-fg"
    >
      {children}
    </button>
  );
}
