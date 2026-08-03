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
}) {
  return (
    <Card className={cn("p-5", className)}>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 font-display text-[28px] font-semibold leading-none tabular-nums",
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
