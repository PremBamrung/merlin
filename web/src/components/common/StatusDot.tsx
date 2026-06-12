import { cn } from "@/lib/utils";

// status → treatment (DESIGN_SYSTEM §2). `failed` reuses the brand red.
const STATUS_COLOR: Record<string, string> = {
  completed: "bg-success",
  processing: "bg-info",
  queued: "bg-fg-subtle",
  pending: "bg-warning",
  failed: "bg-accent",
  unknown: "bg-fg-subtle",
};

export const STATUS_LABEL: Record<string, string> = {
  completed: "Completed",
  processing: "Processing",
  queued: "Queued",
  pending: "Pending",
  failed: "Failed",
};

export function StatusDot({
  status,
  className,
  pulse,
}: {
  status: string | null | undefined;
  className?: string;
  pulse?: boolean;
}) {
  const key = status ?? "unknown";
  return (
    <span className={cn("relative inline-flex size-2 shrink-0", className)}>
      {pulse && (key === "processing" || key === "queued") && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
            STATUS_COLOR[key],
          )}
        />
      )}
      <span
        className={cn(
          "relative inline-flex size-2 rounded-full",
          STATUS_COLOR[key] ?? STATUS_COLOR.unknown,
        )}
      />
    </span>
  );
}
