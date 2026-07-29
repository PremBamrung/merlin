import { useTaskStream } from "@/hooks/useTaskProgress";
import { useActiveTasks } from "@/store/tasks";

function TaskStream({ taskId }: { taskId: string }) {
  useTaskStream(taskId);
  return null;
}

/**
 * Headless: streams every ingest submitted this session, one connection each.
 * Mounted once in the app shell so progress keeps flowing — and the top-bar ring
 * keeps turning — on every route, not only on Today where the task rows live.
 */
export function TaskStreams() {
  const activeIds = useActiveTasks((s) => s.activeIds);
  return activeIds.map((id) => <TaskStream key={id} taskId={id} />);
}
