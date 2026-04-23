import clsx from 'clsx'
import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react'
import type { Task } from '@/types'

interface ProcessingStatusProps {
  task: Task | null
}

const statusConfig = {
  queued: {
    label: 'Queued',
    color: 'text-[#f59e0b]',
    bg: 'bg-[#f59e0b]/10',
    border: 'border-[#f59e0b]/30',
    icon: <Clock size={14} />,
    barColor: 'bg-[#f59e0b]',
  },
  processing: {
    label: 'Processing',
    color: 'text-blue-400',
    bg: 'bg-blue-400/10',
    border: 'border-blue-400/30',
    icon: <Loader2 size={14} className="animate-spin" />,
    barColor: 'bg-blue-400',
  },
  completed: {
    label: 'Completed',
    color: 'text-[#10b981]',
    bg: 'bg-[#10b981]/10',
    border: 'border-[#10b981]/30',
    icon: <CheckCircle size={14} />,
    barColor: 'bg-[#10b981]',
  },
  failed: {
    label: 'Failed',
    color: 'text-[#ef4444]',
    bg: 'bg-[#ef4444]/10',
    border: 'border-[#ef4444]/30',
    icon: <XCircle size={14} />,
    barColor: 'bg-[#ef4444]',
  },
}

export default function ProcessingStatus({ task }: ProcessingStatusProps) {
  if (!task) return null

  const config = statusConfig[task.status]
  const progress = Math.min(100, Math.max(0, task.progress ?? 0))

  return (
    <div className="space-y-3 mt-4">
      {/* Status badge */}
      <div className="flex items-center justify-between">
        <div
          className={clsx(
            'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
            config.color,
            config.bg,
            config.border
          )}
        >
          {config.icon}
          <span>{config.label}</span>
        </div>
        <span className="text-xs text-[#555555]">{progress}%</span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-500',
            config.barColor,
            task.status === 'processing' && progress < 100 && 'animate-pulse'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Message */}
      {task.message && (
        <p className="text-xs text-[#888888]">{task.message}</p>
      )}

      {/* Completed result */}
      {task.status === 'completed' && (
        <div className="flex items-center gap-2 p-3 bg-[#10b981]/10 border border-[#10b981]/30 rounded-lg">
          <CheckCircle size={16} className="text-[#10b981] flex-shrink-0" />
          <div>
            <p className="text-sm text-[#10b981] font-medium">Added to knowledge base</p>
            {task.result?.knowledge_item_id && (
              <p className="text-xs text-[#555555] mt-0.5">
                ID: {task.result.knowledge_item_id}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Failed error */}
      {task.status === 'failed' && (task.error || task.message) && (
        <div className="flex items-start gap-2 p-3 bg-[#ef4444]/10 border border-[#ef4444]/30 rounded-lg">
          <XCircle size={16} className="text-[#ef4444] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[#ef4444]">
            {task.error || task.message}
          </p>
        </div>
      )}
    </div>
  )
}
