import { useState } from "react";
import { useActiveTasks } from "@/store/tasks";

/** Rows shown before the rest collapse behind a "+N more" toggle. */
const VISIBLE = 3;

/**
 * The active ingests in display order, capped at `visible` until expanded.
 * Shared by the Library's strip and the home page's card so both agree on
 * which rows show first.
 */
export function useIngestRows(visible = VISIBLE) {
  const activeIds = useActiveTasks((s) => s.activeIds);
  const frames = useActiveTasks((s) => s.frames);
  const [expanded, setExpanded] = useState(false);

  // `activeIds` is newest-first, but the queue drains oldest-first across three
  // workers — so the newest submissions are precisely the ones still waiting.
  // Truncating that order would hide every task actually doing something. Sort
  // the movers up front (stable, so submission order holds within each group).
  const ordered = [...activeIds].sort(
    (a, b) => queuedRank(frames[a]?.status) - queuedRank(frames[b]?.status),
  );
  const shown = expanded ? ordered : ordered.slice(0, visible);
  return {
    total: ordered.length,
    shown,
    hidden: ordered.length - shown.length,
    expanded,
    toggle: () => setExpanded((e) => !e),
  };
}

/** 0 = moving (or just finished), 1 = still waiting for a worker. */
function queuedRank(status: string | undefined): number {
  return status === "queued" || status === undefined ? 1 : 0;
}
