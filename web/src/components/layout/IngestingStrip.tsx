import { ChevronDown, ChevronUp } from "lucide-react";
import { TaskRow } from "@/components/ingest/TaskRow";
import { useIngestRows } from "@/hooks/useIngestRows";
import { cn } from "@/lib/utils";

/**
 * Live ingest progress in the Library (the home page has its own card, built
 * from the same rows — see `IngestCard` in routes/home.tsx).
 *
 * The ring around the mark says *that* something is ingesting; it averages every task
 * into one arc and can't say what, how far, or which stage. This is where the
 * per-task detail lives — title, pipeline message, percent, and cancel.
 *
 * It sits *below* the page's controls, directly above the results, because it
 * appears and disappears on its own schedule: anchored at the top it shunted
 * the title, search field and every filter chip down the page when an ingest
 * started and back up when it finished. Below them, only the grid moves.
 *
 * Renders nothing when no ingest is in flight, so `className` carries any
 * spacing — a wrapper would leave a phantom gap the rest of the time.
 */
export function IngestingStrip({ className }: { className?: string }) {
  const rows = useIngestRows();
  if (rows.total === 0) return null;

  return (
    <section className={cn("space-y-3", className)}>
      <p className="eyebrow">Ingesting · {rows.total} active</p>

      <div className="space-y-2">
        {rows.shown.map((id) => (
          <TaskRow key={id} taskId={id} />
        ))}
      </div>

      <MoreToggle {...rows} />
    </section>
  );
}

/** "N more" / "Show less" under a capped list of ingest rows. */
export function MoreToggle({
  hidden,
  expanded,
  toggle,
  className,
}: {
  hidden: number;
  expanded: boolean;
  toggle: () => void;
  className?: string;
}) {
  if (hidden === 0 && !expanded) return null;
  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        "flex items-center gap-1 text-[12px] text-fg-muted transition-colors hover:text-fg",
        className,
      )}
    >
      {expanded ? (
        <>
          <ChevronUp className="size-3.5" /> Show less
        </>
      ) : (
        <>
          <ChevronDown className="size-3.5" /> {hidden} more
        </>
      )}
    </button>
  );
}
