import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Eyebrow label + big number tile (Today / Insights). */
export function StatTile({
  label,
  value,
  hint,
  className,
  accent,
  big,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
  accent?: boolean;
  /** Larger number on wide screens (Today hero metrics). */
  big?: boolean;
}) {
  return (
    <Card className={cn("p-5", big && "xl:p-6", className)}>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 font-semibold leading-none tabular-nums",
          big ? "text-[28px] 2xl:text-[36px]" : "text-[28px]",
          accent ? "text-accent" : "text-fg",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-1.5 text-[12px] text-fg-muted">{hint}</p>}
    </Card>
  );
}
