import clsx from 'clsx'
import { Youtube, FileText, BookOpen, Calendar, AlertCircle, Loader2 } from 'lucide-react'
import type { KnowledgeItem } from '@/types'

interface KnowledgeCardProps {
  item: KnowledgeItem
  onClick: (item: KnowledgeItem) => void
}

const sourceIcons = {
  youtube: <Youtube size={12} />,
  article: <FileText size={12} />,
  pdf: <BookOpen size={12} />,
}

const statusConfig = {
  pending: { label: 'Pending', className: 'text-[#555555] bg-[#555555]/10 border-[#555555]/30' },
  processing: { label: 'Processing', className: 'text-blue-400 bg-blue-400/10 border-blue-400/30' },
  completed: null, // don't show badge for completed
  failed: { label: 'Failed', className: 'text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/30' },
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export default function KnowledgeCard({ item, onClick }: KnowledgeCardProps) {
  const thumbnail =
    item.thumbnail_url ||
    (item.source_type === 'youtube' && item.source_id
      ? `https://img.youtube.com/vi/${item.source_id}/hqdefault.jpg`
      : null)

  const authorLabel = item.channel || item.author

  const statusBadge = item.status !== 'completed' ? statusConfig[item.status] : null

  return (
    <div
      onClick={() => onClick(item)}
      className={clsx(
        'group bg-[#161616] rounded-xl border border-[#2a2a2a] hover:border-[#3d3d3d]',
        'transition-all duration-200 cursor-pointer overflow-hidden',
        'flex flex-col'
      )}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-[#1f1f1f] overflow-hidden flex-shrink-0">
        {thumbnail ? (
          <img
            src={thumbnail}
            alt={item.title}
            className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
            loading="lazy"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = 'none'
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="w-10 h-10 rounded-full bg-[#2a2a2a] flex items-center justify-center">
              <span className="text-[#555555]">
                {sourceIcons[item.source_type] || <FileText size={20} />}
              </span>
            </div>
          </div>
        )}

        {/* Source type badge */}
        <div className="absolute top-2 left-2">
          <span className={clsx(
            'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium',
            item.source_type === 'youtube'
              ? 'bg-red-500/80 text-white'
              : 'bg-[#1f1f1f]/80 text-[#888888]',
            'backdrop-blur-sm'
          )}>
            {sourceIcons[item.source_type]}
            <span className="capitalize">{item.source_type}</span>
          </span>
        </div>

        {/* Status overlay for non-completed */}
        {item.status === 'processing' && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <Loader2 size={24} className="text-blue-400 animate-spin" />
          </div>
        )}
        {item.status === 'failed' && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
            <AlertCircle size={24} className="text-[#ef4444]" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3 flex flex-col gap-2 flex-1">
        {/* Title */}
        <h3 className="text-sm font-medium text-[#e8e8e8] line-clamp-2 leading-snug group-hover:text-white transition-colors">
          {item.title || 'Untitled'}
        </h3>

        {/* Author / channel */}
        {authorLabel && (
          <p className="text-xs text-[#555555] truncate">{authorLabel}</p>
        )}

        {/* Date + status */}
        <div className="flex items-center justify-between mt-auto pt-1">
          <div className="flex items-center gap-1 text-[#555555]">
            <Calendar size={11} />
            <span className="text-[11px]">{formatDate(item.ingested_at)}</span>
          </div>

          {statusBadge && (
            <span className={clsx(
              'inline-flex px-1.5 py-0.5 rounded border text-[10px] font-medium',
              statusBadge.className
            )}>
              {statusBadge.label}
            </span>
          )}
        </div>

        {/* Tags */}
        {item.tags && item.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 rounded border border-[#7c3aed]/40 text-[#a78bfa] text-[10px] font-medium"
              >
                {tag}
              </span>
            ))}
            {item.tags.length > 3 && (
              <span className="px-1.5 py-0.5 rounded border border-[#2a2a2a] text-[#555555] text-[10px]">
                +{item.tags.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
