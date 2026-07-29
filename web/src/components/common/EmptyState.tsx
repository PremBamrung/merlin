import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Empty state — icon + one line + a single primary action. Never a dead end. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[12px] border border-dashed border-border px-6 py-16 text-center",
        className,
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-surface-2 text-fg-subtle">
        <Icon className="size-6" strokeWidth={1.5} />
      </div>
      <div className="space-y-1">
        <p className="font-display text-[15px] font-medium text-fg">{title}</p>
        {description && (
          <p className="mx-auto max-w-sm text-sm text-fg-muted">{description}</p>
        )}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
