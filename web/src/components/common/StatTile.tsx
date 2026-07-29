import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** A number-as-display tile: mono eyebrow + the figure in the display face. */
export function StatTile({
  label,
  value,
  hint,
  className,
  tone = "default",
  big,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
  /**
   * `accent` highlights a figure worth noticing (indigo — structural);
   * `fail` is for a count of things that broke (rust). Never gold: the tile is
   * a number, not a state that wants acting on.
   */
  tone?: "default" | "accent" | "fail";
  /** Larger number on wide screens (Today hero metrics). */
  big?: boolean;
}) {
  return (
    <Card className={cn("p-5", big && "xl:p-6", className)}>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 font-display font-semibold leading-none tabular-nums",
          big ? "text-[28px] 2xl:text-[36px]" : "text-[28px]",
          tone === "accent"
            ? "text-accent-lit"
            : tone === "fail"
              ? "text-fail"
              : "text-fg",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-1.5 text-[12px] text-fg-muted">{hint}</p>}
    </Card>
  );
}
