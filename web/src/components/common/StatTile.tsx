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
   * `emphasis` lifts a figure worth noticing (near-white — structural);
   * `fail` is for a count of things that broke (rust). Never gold: the tile is
   * a number, not a state that wants acting on.
   */
  tone?: "default" | "emphasis" | "fail";
}) {
  return (
    <Card className={cn("p-5", className)}>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 font-display text-[28px] font-semibold leading-none tabular-nums",
          tone === "emphasis"
            ? "text-ui-link"
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
