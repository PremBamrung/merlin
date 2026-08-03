import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useActiveTasks } from "@/store/tasks";
import { TaskRow } from "@/components/ingest/TaskRow";
import { cn } from "@/lib/utils";

/** Rows shown before the rest collapse behind a "+N more" toggle. */
const VISIBLE = 3;

/**
 * Live ingest progress, for every route.
 *
 * The top-bar ring says *that* something is ingesting; it averages every task
 * into one arc and can't say what, how far, or which stage. This is where the
 * per-task detail lives — title, pipeline message, percent, and the only cancel
 * button in the app.
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
  const activeIds = useActiveTasks((s) => s.activeIds);
  const frames = useActiveTasks((s) => s.frames);
  const [expanded, setExpanded] = useState(false);

  if (activeIds.length === 0) return null;

  // `activeIds` is newest-first, but the queue drains oldest-first across three
  // workers — so the newest submissions are precisely the ones still waiting.
  // Truncating that order would hide every task actually doing something. Sort
  // the movers up front (stable, so submission order holds within each group).
  const ordered = [...activeIds].sort(
    (a, b) => queuedRank(frames[a]?.status) - queuedRank(frames[b]?.status),
  );
  const shown = expanded ? ordered : ordered.slice(0, VISIBLE);
  const hidden = ordered.length - shown.length;

  return (
    <section className={cn("space-y-3", className)}>
      <p className="eyebrow">Ingesting · {activeIds.length} active</p>

      <div className="space-y-2">
        {shown.map((id) => (
          <TaskRow key={id} taskId={id} />
        ))}
      </div>

      {(hidden > 0 || expanded) && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1 text-[12px] text-fg-muted transition-colors hover:text-fg"
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
      )}
    </section>
  );
}

/** 0 = moving (or just finished), 1 = still waiting for a worker. */
function queuedRank(status: string | undefined): number {
  return status === "queued" || status === undefined ? 1 : 0;
}
