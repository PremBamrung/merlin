import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { Mark } from "@/components/brand/Mark";
import { cn } from "@/lib/utils";

/**
 * Empty state (mockup `.empty`): an icon tile, a title, one line, the way
 * forward. Never a dead end. `icon="hat"` uses the mark — for the moments
 * that are Merlin's own (first run, all caught up); `badge` sits on the
 * tile's corner (the caught-up ✓); `tone` tints the icon gold or rust.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  badge,
  tone,
  className,
  children,
}: {
  icon: LucideIcon | "hat";
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  badge?: ReactNode;
  tone?: "gold" | "err";
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "mx-auto flex max-w-[560px] flex-col items-center gap-2.5 px-6 py-12 text-center",
        className,
      )}
    >
      <div
        className={cn(
          "relative mb-1.5 grid size-14 place-items-center rounded-2xl border border-border-strong bg-surface text-ui-icon",
          Icon === "hat" && "size-[92px] rounded-[22px]",
          tone === "gold" && "text-signal",
          tone === "err" && "text-fail",
        )}
      >
        {Icon === "hat" ? <Mark size={52} decorative /> : <Icon className="size-[26px]" strokeWidth={1.6} />}
        {badge && <span className="absolute -bottom-1 -right-1">{badge}</span>}
      </div>
      <h2 className="font-display text-[22px] font-semibold leading-7 tracking-[-0.02em] text-fg">{title}</h2>
      {description && <p className="text-[15px] leading-[23px] text-fg-muted">{description}</p>}
      {action && <div className="mt-2.5 flex flex-wrap justify-center gap-2">{action}</div>}
      {children}
    </div>
  );
}
