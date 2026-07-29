import { cn } from "@/lib/utils";

/**
 * status → treatment. Gold is "what wants you", so it marks the one status that
 * is actually happening now; waiting states stay grey and failure is rust.
 * `--color-warning` and `--color-info` were retired with the red palette — the
 * amber sat ~6° from the gold and read as a second signal.
 *
 * A dot is never the only channel: every caller pairs it with `STATUS_LABEL` or
 * its own text, because rust and green are ΔE 4.7 apart under deuteranopia.
 */
const STATUS_COLOR: Record<string, string> = {
  completed: "bg-success",
  processing: "bg-signal",
  queued: "bg-fg-subtle",
  pending: "bg-fg-muted",
  failed: "bg-fail",
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
