import { create } from "zustand";
import type { Task } from "@/lib/api/endpoints";

/** The latest streamed state of one task. */
export type TaskFrameState = { task: Task | null; status: string };

/**
 * Tracks task IDs submitted during this session, plus the latest SSE frame for
 * each. Terminal tasks are dropped once acknowledged.
 *
 * The frames live here rather than inside the component that renders them
 * because **two** surfaces show the same progress — the Today task panel and the
 * ingest ring around the top-bar mark — and a task must only ever be streamed
 * once (each stream is an open connection, and browsers cap those per origin).
 * `TaskStreams` in hooks/useTaskProgress.tsx is the single writer; everything
 * else reads.
 */
type TaskStore = {
  activeIds: string[];
  frames: Record<string, TaskFrameState>;
  add: (id: string) => void;
  remove: (id: string) => void;
  setFrame: (id: string, frame: TaskFrameState) => void;
};

export const useActiveTasks = create<TaskStore>((set) => ({
  activeIds: [],
  frames: {},
  add: (id) =>
    set((s) => (s.activeIds.includes(id) ? s : { activeIds: [id, ...s.activeIds] })),
  remove: (id) =>
    set((s) => {
      const frames = { ...s.frames };
      delete frames[id];
      return { activeIds: s.activeIds.filter((x) => x !== id), frames };
    }),
  setFrame: (id, frame) => set((s) => ({ frames: { ...s.frames, [id]: frame } })),
}));
