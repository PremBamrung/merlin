import { NavLink } from "react-router-dom";
import {
  Home,
  Library,
  Layers,
  MessageSquare,
  BarChart3,
  MonitorPlay,
  type LucideIcon,
} from "lucide-react";
import { useSourceTypes, useLibraryCount } from "@/hooks/useMeta";
import { useUnreadCount } from "@/hooks/useFeed";
import { thousands } from "@/lib/format";
import { cn } from "@/lib/utils";

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean };

const WORKSPACE: NavItem[] = [
  { to: "/", label: "Today", icon: Home, end: true },
  { to: "/feed", label: "Feed", icon: Layers },
  { to: "/library", label: "Library", icon: Library },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/insights", label: "Insights", icon: BarChart3 },
];

const SOURCE_ICON: Record<string, LucideIcon> = { youtube: MonitorPlay };

function Item({
  item,
  count,
  alert,
  onNavigate,
}: {
  item: NavItem;
  count?: number;
  alert?: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors",
          isActive
            ? "bg-accent-subtle text-fg"
            : "text-fg-muted hover:bg-surface-2 hover:text-fg",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-accent" />
          )}
          <Icon className="size-4 shrink-0" strokeWidth={1.5} />
          <span className="flex-1 truncate">{item.label}</span>
          {count !== undefined &&
            (alert ? (
              <span className="flex min-w-4 items-center justify-center rounded-full bg-accent px-1 font-mono text-[10px] tabular-nums text-accent-fg">
                {count}
              </span>
            ) : (
              <span className="font-mono text-[11px] tabular-nums text-fg-subtle">
                {thousands(count)}
              </span>
            ))}
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({
  className,
  onNavigate,
}: {
  className?: string;
  onNavigate?: () => void;
}) {
  const sourceTypes = useSourceTypes();
  const libraryCount = useLibraryCount();
  const unread = useUnreadCount();

  return (
    <aside
      className={cn(
        "flex h-full w-[240px] shrink-0 flex-col border-r border-border bg-surface/40",
        className,
      )}
    >
      <div className="flex h-14 items-center gap-2 px-5">
        <span className="text-accent">✦</span>
        <span className="text-[15px] font-semibold tracking-tight">Merlin</span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
        <div className="space-y-0.5">
          <p className="eyebrow px-2.5 pb-1">Workspace</p>
          {WORKSPACE.map((item) => (
            <Item
              key={item.to}
              item={item}
              onNavigate={onNavigate}
              count={
                item.to === "/library"
                  ? libraryCount.data
                  : item.to === "/feed"
                    ? unread.data || undefined
                    : undefined
              }
            />
          ))}
        </div>

        {(sourceTypes.data?.length ?? 0) > 0 && (
          <div className="space-y-0.5">
            <p className="eyebrow px-2.5 pb-1">Sources</p>
            {sourceTypes.data!.map((s) => (
              <Item
                key={s.name}
                onNavigate={onNavigate}
                item={{
                  to: `/library?source_type=${s.name}`,
                  label: s.name.charAt(0).toUpperCase() + s.name.slice(1),
                  icon: SOURCE_ICON[s.name] ?? Library,
                }}
                count={s.count}
              />
            ))}
          </div>
        )}
      </nav>

      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-7 items-center justify-center rounded-full bg-surface-2 text-[11px] text-fg-muted">
            ◐
          </span>
          <span className="text-[13px] text-fg-muted">prem</span>
        </div>
      </div>
    </aside>
  );
}
