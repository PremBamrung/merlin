import client from './client'
import type { Task } from '@/types'

export async function fetchTask(taskId: string): Promise<Task> {
  const response = await client.get<Task>(`/api/tasks/${taskId}`)
  return response.data
}

/**
 * Poll a task every 1.5 seconds until it completes or fails.
 * Returns a cleanup function to stop polling.
 */
export function pollTask(
  taskId: string,
  onProgress: (task: Task) => void,
  onDone: (task: Task) => void,
  onError: (err: string) => void
): () => void {
  let stopped = false
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  async function poll() {
    if (stopped) return

    try {
      const task = await fetchTask(taskId)
      onProgress(task)

      if (task.status === 'completed') {
        onDone(task)
        return
      }

      if (task.status === 'failed') {
        onError(task.error || task.message || 'Task failed')
        return
      }

      // Still queued or processing — schedule next poll
      if (!stopped) {
        timeoutId = setTimeout(poll, 1500)
      }
    } catch (err) {
      if (!stopped) {
        const message = err instanceof Error ? err.message : 'Failed to fetch task status'
        onError(message)
      }
    }
  }

  // Start polling immediately
  poll()

  // Return cleanup function
  return () => {
    stopped = true
    if (timeoutId !== null) {
      clearTimeout(timeoutId)
    }
  }
}
