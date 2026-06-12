import { create } from "zustand";

/**
 * Tracks task IDs submitted during this session so the Today task panel can
 * stream live progress for them. Terminal tasks are dropped once acknowledged.
 */
type TaskStore = {
  activeIds: string[];
  add: (id: string) => void;
  remove: (id: string) => void;
};

export const useActiveTasks = create<TaskStore>((set) => ({
  activeIds: [],
  add: (id) =>
    set((s) => (s.activeIds.includes(id) ? s : { activeIds: [id, ...s.activeIds] })),
  remove: (id) => set((s) => ({ activeIds: s.activeIds.filter((x) => x !== id) })),
}));
