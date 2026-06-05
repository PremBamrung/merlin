import client from './client'
import type { Task } from '@/types'

export async function fetchTasks(limit = 20): Promise<Task[]> {
  const res = await client.get<Task[]>('/api/tasks', { params: { limit } })
  return res.data
}

export async function fetchTask(taskId: string): Promise<Task> {
  const res = await client.get<Task>(`/api/tasks/${taskId}`)
  return res.data
}

export async function deleteTask(taskId: string): Promise<{ ok: boolean }> {
  const res = await client.delete<{ ok: boolean }>(`/api/tasks/${taskId}`)
  return res.data
}

/** Bulk-clear tasks. Defaults to clearing failed ingestions. */
export async function clearTasks(status: string = 'failed'): Promise<{ deleted: number }> {
  const res = await client.delete<{ deleted: number }>('/api/tasks', { params: { status } })
  return res.data
}

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
      if (task.status === 'completed') { onDone(task); return }
      if (task.status === 'failed') { onError(task.error || task.message || 'Task failed'); return }
      if (!stopped) timeoutId = setTimeout(poll, 1500)
    } catch (err) {
      if (!stopped) onError(err instanceof Error ? err.message : 'Failed to fetch task status')
    }
  }

  poll()
  return () => {
    stopped = true
    if (timeoutId !== null) clearTimeout(timeoutId)
  }
}
