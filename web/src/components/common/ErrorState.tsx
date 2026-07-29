import { AlertTriangle, RotateCw } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/** Error state — what failed + a retry. For ingest failures, pass the real message. */
export function ErrorState({
  error,
  onRetry,
  title = "Couldn't load this",
  className,
}: {
  error?: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[12px] border border-fail/40 bg-fail/10 px-6 py-12 text-center",
        className,
      )}
    >
      <AlertTriangle className="size-6 text-fail" strokeWidth={1.5} />
      <div className="space-y-1">
        <p className="text-[15px] font-medium text-fg">{title}</p>
        {error !== undefined && (
          <p className="mx-auto max-w-md text-sm text-fg-muted">{messageFor(error)}</p>
        )}
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RotateCw className="size-4" /> Retry
        </Button>
      )}
    </div>
  );
}
