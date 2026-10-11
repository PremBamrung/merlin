import type { ReactNode } from "react";
import { Link, type To } from "react-router-dom";
import { Search, type LucideIcon } from "lucide-react";
import { useUi } from "@/store/ui";
import { thousands } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Building blocks every place's panel is made of — so the panels read as one
 *  system (mockup: `.sb-group`, `.sb-row`, `.pn-find`). */

export function PanelSection({
  title,
  right,
  children,
}: {
  title: ReactNode;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center gap-2 px-2.5 pb-2 pt-4 font-mono text-[11px] font-medium uppercase leading-none tracking-[0.08em] text-fg-subtle">
        {title}
        {right && (
          <span className="ml-auto normal-case tracking-normal text-ui-link">{right}</span>
        )}
      </div>
      <div className="space-y-px">{children}</div>
    </section>
  );
}

type RowProps = {
  label: ReactNode;
  icon?: LucideIcon;
  /** Replaces the icon — a channel avatar, a gold dot, a thumbnail. */
  lead?: ReactNode;
  count?: number | string | null;
  /** Gold count: unread — the only thing allowed to wear it here. */
  gold?: boolean;
  /** Trailing marker instead of a count (e.g. an unread dot). */
  trail?: ReactNode;
  on?: boolean;
  title?: string;
};

function RowBody({ label, icon: Icon, lead, count, gold, trail, on }: RowProps) {
  return (
    <>
      {lead ??
        (Icon && (
          <Icon
            className={cn("size-4 shrink-0", on ? "text-ui-current-fg" : "text-fg-subtle")}
            strokeWidth={1.75}
          />
        ))}
      <span className="min-w-0 truncate">{label}</span>
      {trail ??
        (count != null && (
          <span
            className={cn(
              "ml-auto shrink-0 font-mono text-[11px] tabular-nums",
              gold ? "font-medium text-signal" : "text-fg-subtle",
            )}
          >
            {typeof count === "number" ? thousands(count) : count}
          </span>
        ))}
    </>
  );
}

const rowClass = (on?: boolean) =>
  cn(
    "flex h-[34px] w-full items-center gap-[11px] rounded-md px-2.5 text-left text-[14px] transition-colors",
    on ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface hover:text-fg",
  );

export function PanelLink({ to, ...p }: RowProps & { to: To }) {
  return (
    <Link to={to} className={rowClass(p.on)} aria-current={p.on ? "page" : undefined} title={p.title}>
      <RowBody {...p} />
    </Link>
  );
}

export function PanelButton({ onClick, ...p }: RowProps & { onClick: () => void }) {
  return (
    <button onClick={onClick} className={rowClass(p.on)} aria-pressed={p.on} title={p.title}>
      <RowBody {...p} />
    </button>
  );
}

/** Opens the ⌘K palette — the panel's "Search …" field is a door, not an input. */
export function PanelSearch({ placeholder }: { placeholder: string }) {
  const setPaletteOpen = useUi((s) => s.setPaletteOpen);
  const isMac = navigator.platform.toLowerCase().includes("mac");
  return (
    <button
      onClick={() => setPaletteOpen(true)}
      className="flex h-9 w-full items-center gap-[9px] rounded-md border border-border px-2.5 text-[14px] text-fg-subtle transition-colors hover:border-border-strong hover:text-fg"
    >
      <Search className="size-4" />
      {placeholder}
      <Kbd className="ml-auto">{isMac ? "⌘ K" : "Ctrl K"}</Kbd>
    </button>
  );
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "rounded border border-border-strong px-1.5 py-0.5 font-mono text-[10px] leading-none text-fg-subtle",
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Initials avatar for a channel row. */
export function ChannelAvatar({ name }: { name: string }) {
  const ini = name
    .replace(/[^\p{L}\p{N} ]/gu, "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  return (
    <span className="grid size-[22px] shrink-0 place-items-center rounded-full border border-border-strong bg-surface-2 font-display text-[10px] font-semibold text-fg">
      {ini || "·"}
    </span>
  );
}
