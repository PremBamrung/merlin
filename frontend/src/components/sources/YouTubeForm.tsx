import { useState } from 'react'
import { Youtube, ArrowRight, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import { submitYouTube } from '@/api/youtube'
import { pollTask } from '@/api/tasks'
import ProcessingStatus from './ProcessingStatus'
import type { Task } from '@/types'
import { useQueryClient } from '@tanstack/react-query'

type SummaryLength = 'short' | 'medium' | 'long'

const summaryOptions: { value: SummaryLength; label: string; desc: string }[] = [
  { value: 'short', label: 'Short', desc: '~150 words' },
  { value: 'medium', label: 'Medium', desc: '~300 words' },
  { value: 'long', label: 'Long', desc: '~500 words' },
]

export default function YouTubeForm() {
  const [url, setUrl] = useState('')
  const [summaryLength, setSummaryLength] = useState<SummaryLength>('medium')
  const [task, setTask] = useState<Task | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stopPolling, setStopPolling] = useState<(() => void) | null>(null)

  const queryClient = useQueryClient()

  const isProcessing = task !== null && task.status !== 'completed' && task.status !== 'failed'
  const isDone = task?.status === 'completed'
  const isFailed = task?.status === 'failed'

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!url.trim() || submitting || isProcessing) return

    setError(null)
    setTask(null)
    setSubmitting(true)

    try {
      const result = await submitYouTube(url.trim(), summaryLength)

      // Create initial task state
      const initialTask: Task = {
        task_id: result.task_id,
        status: 'queued',
        progress: 0,
        message: 'Task queued...',
      }
      setTask(initialTask)
      setSubmitting(false)

      // Start polling
      const cleanup = pollTask(
        result.task_id,
        (updatedTask) => {
          setTask(updatedTask)
        },
        (doneTask) => {
          setTask(doneTask)
          // Invalidate knowledge query so the list refreshes
          queryClient.invalidateQueries({ queryKey: ['knowledge'] })
        },
        (err) => {
          setTask((prev) =>
            prev
              ? { ...prev, status: 'failed', error: err }
              : { task_id: result.task_id, status: 'failed', progress: 0, message: err, error: err }
          )
        }
      )
      setStopPolling(() => cleanup)
    } catch (err) {
      setSubmitting(false)
      setError(err instanceof Error ? err.message : 'Failed to submit URL')
    }
  }

  function handleClear() {
    if (stopPolling) {
      stopPolling()
      setStopPolling(null)
    }
    setUrl('')
    setTask(null)
    setError(null)
    setSubmitting(false)
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* URL input */}
        <div>
          <label className="block text-xs font-medium text-[#888888] mb-1.5">
            YouTube URL
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Youtube size={16} className="text-[#555555]" />
            </div>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtube.com/watch?v=..."
              disabled={isProcessing || submitting}
              className={clsx(
                'w-full pl-9 pr-4 py-2.5 bg-[#1f1f1f] border rounded-lg text-sm text-[#e8e8e8]',
                'placeholder:text-[#555555] outline-none transition-colors',
                'focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]/30',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                error ? 'border-[#ef4444]' : 'border-[#2a2a2a]'
              )}
            />
          </div>
          {error && (
            <p className="mt-1 text-xs text-[#ef4444]">{error}</p>
          )}
        </div>

        {/* Summary length */}
        <div>
          <label className="block text-xs font-medium text-[#888888] mb-1.5">
            Summary Length
          </label>
          <div className="grid grid-cols-3 gap-2">
            {summaryOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setSummaryLength(opt.value)}
                disabled={isProcessing || submitting}
                className={clsx(
                  'px-3 py-2 rounded-lg border text-sm transition-all duration-150',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  summaryLength === opt.value
                    ? 'border-[#7c3aed] bg-[#7c3aed]/20 text-[#a78bfa]'
                    : 'border-[#2a2a2a] bg-[#1f1f1f] text-[#888888] hover:border-[#3d3d3d] hover:text-[#e8e8e8]'
                )}
              >
                <div className="font-medium">{opt.label}</div>
                <div className="text-xs opacity-60">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Submit / Clear buttons */}
        <div className="flex gap-2 pt-1">
          {(isDone || isFailed) ? (
            <button
              type="button"
              onClick={handleClear}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#1f1f1f] hover:bg-[#2a2a2a] border border-[#2a2a2a] text-[#e8e8e8] text-sm font-medium rounded-lg transition-colors"
            >
              <RotateCcw size={14} />
              Add Another
            </button>
          ) : (
            <button
              type="submit"
              disabled={!url.trim() || submitting || isProcessing}
              className={clsx(
                'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-colors',
                'bg-[#7c3aed] hover:bg-[#6d28d9] text-white',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {submitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <ArrowRight size={16} />
                  Process Video
                </>
              )}
            </button>
          )}
        </div>
      </form>

      {/* Task status */}
      <ProcessingStatus task={task} />

      {/* Success: link to knowledge item */}
      {isDone && task?.result?.knowledge_item_id && (
        <div className="mt-3 text-center">
          <a
            href={`/knowledge`}
            className="text-xs text-[#7c3aed] hover:text-[#a78bfa] underline underline-offset-2"
          >
            View in Knowledge Base →
          </a>
        </div>
      )}
    </div>
  )
}
