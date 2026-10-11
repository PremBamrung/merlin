import { cn } from "@/lib/utils";

/** Shimmering placeholder. Compose these to mirror the final layout. */
export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        // Raised, not surface-2: it has to read on the card surface too, where
        // surface-2 is barely a step up (the mockup's loading frames).
        "relative overflow-hidden rounded-md bg-surface-raised/70",
        "after:absolute after:inset-0 after:-translate-x-full after:animate-[shimmer_1.6s_infinite]",
        "after:bg-gradient-to-r after:from-transparent after:via-white/[0.05] after:to-transparent",
        className,
      )}
      {...props}
    />
  );
}
