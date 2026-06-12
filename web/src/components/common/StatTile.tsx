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
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
  accent?: boolean;
}) {
  return (
    <Card className={cn("p-5", className)}>
      <p className="eyebrow">{label}</p>
      <p
        className={cn(
          "mt-2 text-[28px] font-semibold leading-none tabular-nums",
          accent ? "text-accent" : "text-fg",
        )}
      >
        {value}
      </p>
      {hint && <p className="mt-1.5 text-[12px] text-fg-muted">{hint}</p>}
    </Card>
  );
}
