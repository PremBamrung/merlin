import { Link, NavLink } from "react-router-dom";
import { PanelLeft, Plus, Search } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { IngestRing } from "./IngestRing";
import { PLACES } from "./places";
import { useIngestActivity } from "@/hooks/useTaskProgress";
import { useUnreadCount } from "@/hooks/useFeed";
import { useUi } from "@/store/ui";
import { cn } from "@/lib/utils";

/**
 * The icon rail: the ONLY navigation on desktop (mockup `.rail`). The mark on
 * top carries the ingest ring; the places sit below it; the bottom holds the
 * global tools (search, add, panel). The Feed's gold count is one of the few
 * things allowed to be gold — it says something wants you.
 *
 * Settings + avatar from the mockup land with the Settings place (Phase 1).
 */
export function Rail({ panelOpen, onTogglePanel }: { panelOpen: boolean; onTogglePanel: () => void }) {
  const unread = useUnreadCount().data ?? 0;
  const { running } = useIngestActivity();
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const openAdd = useUi((s) => s.openAdd);
  const isMac = navigator.platform.toLowerCase().includes("mac");
  const ingestLabel = running > 0 ? `${running} ingest${running === 1 ? "" : "s"} running` : undefined;

  return (
    <nav
      aria-label="Places"
      className="z-20 flex w-[68px] shrink-0 flex-col items-center gap-1 border-r border-border bg-ui-rail-bg py-3"
    >
      <Link
        to="/"
        className="mb-2.5 grid size-11 place-items-center rounded-xl transition-colors hover:bg-surface"
        aria-label={ingestLabel ? `Merlin — home (${ingestLabel})` : "Merlin — home"}
        title={ingestLabel}
      >
        <span className="relative flex items-center justify-center">
          <Mark size={26} decorative />
          <IngestRing size={26} />
        </span>
      </Link>

      {PLACES.map((p) => (
        <NavLink
          key={p.id}
          to={p.to}
          className={({ isActive }) =>
            cn(
              "group relative flex w-[54px] flex-col items-center gap-1 rounded-[11px] pb-[7px] pt-2 text-[10.5px] font-medium leading-3 transition-colors",
              isActive
                ? "bg-ui-current-bg text-fg shadow-[inset_0_0_0_1px_var(--color-ui-current-border),0_1px_2px_rgb(0_0_0/0.35)]"
                : "text-fg-subtle hover:bg-surface hover:text-fg",
            )
          }
        >
          {({ isActive }) => (
            <>
              <p.icon
                className={cn("size-5", isActive && "text-ui-current-fg")}
                strokeWidth={1.75}
              />
              {p.label}
              {p.id === "feed" && unread > 0 && (
                <span
                  className="absolute right-[5px] top-[3px] h-[17px] min-w-[17px] rounded-full bg-signal px-1 text-center font-mono text-[10px] font-semibold leading-[17px] text-bg shadow-[0_0_0_2px_var(--color-ui-rail-bg)]"
                  aria-label={`${unread} unread`}
                >
                  {unread > 99 ? "99+" : unread}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}

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
