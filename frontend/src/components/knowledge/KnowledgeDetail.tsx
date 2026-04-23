import { useEffect, useRef, useState } from 'react'
import {
  X,
  Youtube,
  FileText,
  BookOpen,
  Calendar,
  Eye,
  Clock,
  Hash,
  Cpu,
  Plus,
  Trash2,
  ExternalLink,
} from 'lucide-react'
import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { KnowledgeItem } from '@/types'

interface KnowledgeDetailProps {
  item: KnowledgeItem | null
  onClose: () => void
  onDelete?: (id: string) => void
}

const sourceIcons = {
  youtube: <Youtube size={16} className="text-red-400" />,
  article: <FileText size={16} className="text-blue-400" />,
  pdf: <BookOpen size={16} className="text-orange-400" />,
}

function MetaRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number | null | undefined }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-[#555555] flex-shrink-0">{icon}</span>
      <span className="text-[#555555]">{label}:</span>
      <span className="text-[#888888]">{value}</span>
    </div>
  )
}

function formatDate(dateStr: string | null | undefined) {
  if (!dateStr) return null
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatViews(views: number | null | undefined): string | null {
  if (!views && views !== 0) return null
  if (views >= 1_000_000) return `${(views / 1_000_000).toFixed(1)}M views`
  if (views >= 1_000) return `${(views / 1_000).toFixed(1)}K views`
  return `${views} views`
}

export default function KnowledgeDetail({ item, onClose, onDelete }: KnowledgeDetailProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [tags, setTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const [addingTag, setAddingTag] = useState(false)

  useEffect(() => {
    setTags(item?.tags ?? [])
    setNewTag('')
    setAddingTag(false)
  }, [item])

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  function addTag() {
    const trimmed = newTag.trim().toLowerCase()
    if (trimmed && !tags.includes(trimmed)) {
      setTags([...tags, trimmed])
    }
    setNewTag('')
    setAddingTag(false)
  }

  function removeTag(tag: string) {
    setTags(tags.filter((t) => t !== tag))
  }

  const thumbnail =
    item?.thumbnail_url ||
    (item?.source_type === 'youtube' && item?.source_id
      ? `https://img.youtube.com/vi/${item.source_id}/hqdefault.jpg`
      : null)

  const youtubeUrl = item?.source_type === 'youtube' && item?.source_id
    ? `https://www.youtube.com/watch?v=${item.source_id}`
    : null

  return (
    <>
      {/* Backdrop */}
      <div
        className={clsx(
          'fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity duration-300',
          item ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div
        ref={panelRef}
        className={clsx(
          'fixed top-0 right-0 z-50 h-full w-full max-w-xl bg-[#161616] border-l border-[#2a2a2a]',
          'flex flex-col shadow-2xl transition-transform duration-300 ease-out',
          item ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {item && (
          <>
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
              <div className="flex items-center gap-2">
                {sourceIcons[item.source_type]}
                <span className="text-xs font-medium text-[#555555] capitalize">
                  {item.source_type}
                </span>
              </div>
              <div className="flex items-center gap-1">
                {youtubeUrl && (
                  <a
                    href={youtubeUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg text-[#555555] hover:text-[#e8e8e8] hover:bg-[#2a2a2a] transition-colors"
                    title="Open on YouTube"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
                {onDelete && (
                  <button
                    onClick={() => { onDelete(item.id); onClose() }}
                    className="p-1.5 rounded-lg text-[#555555] hover:text-[#ef4444] hover:bg-[#ef4444]/10 transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-[#555555] hover:text-[#e8e8e8] hover:bg-[#2a2a2a] transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto">
              {/* Thumbnail */}
              {thumbnail && (
                <div className="aspect-video bg-[#0d0d0d] overflow-hidden flex-shrink-0">
                  <img
                    src={thumbnail}
                    alt={item.title}
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              <div className="px-5 py-5 space-y-5">
                {/* Title */}
                <div>
                  <h2 className="text-lg font-semibold text-[#e8e8e8] leading-snug">
                    {item.title || 'Untitled'}
                  </h2>
                  {(item.channel || item.author) && (
                    <p className="mt-1 text-sm text-[#555555]">
                      {item.channel || item.author}
                    </p>
                  )}
                </div>

                {/* Metadata grid */}
                <div className="space-y-1.5 p-3 bg-[#1f1f1f] rounded-lg border border-[#2a2a2a]">
                  <MetaRow icon={<Calendar size={13} />} label="Added" value={formatDate(item.ingested_at)} />
                  <MetaRow icon={<Calendar size={13} />} label="Published" value={formatDate(item.published_at)} />
                  <MetaRow icon={<Eye size={13} />} label="Views" value={formatViews(item.views)} />
                  <MetaRow icon={<Clock size={13} />} label="Duration" value={item.duration} />
                  <MetaRow icon={<Hash size={13} />} label="Words" value={item.word_count ? `${item.word_count.toLocaleString()} words` : null} />
                  <MetaRow icon={<Cpu size={13} />} label="Model" value={item.llm_model} />
                </div>

                {/* Tags */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-[#555555] uppercase tracking-wide">Tags</span>
                    <button
                      onClick={() => setAddingTag(true)}
                      className="p-1 rounded text-[#555555] hover:text-[#a78bfa] hover:bg-[#7c3aed]/10 transition-colors"
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="group/tag inline-flex items-center gap-1 px-2 py-0.5 rounded border border-[#7c3aed]/40 text-[#a78bfa] text-xs font-medium"
                      >
                        {tag}
                        <button
                          onClick={() => removeTag(tag)}
                          className="opacity-0 group-hover/tag:opacity-100 transition-opacity text-[#555555] hover:text-[#ef4444]"
                        >
                          <X size={10} />
                        </button>
                      </span>
                    ))}
                    {tags.length === 0 && !addingTag && (
                      <span className="text-xs text-[#555555]">No tags</span>
                    )}
                    {addingTag && (
                      <input
                        autoFocus
                        type="text"
                        value={newTag}
                        onChange={(e) => setNewTag(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') { e.preventDefault(); addTag() }
                          if (e.key === 'Escape') { setAddingTag(false); setNewTag('') }
                        }}
                        onBlur={addTag}
                        placeholder="add tag..."
                        className="px-2 py-0.5 bg-[#1f1f1f] border border-[#7c3aed]/40 rounded text-xs text-[#e8e8e8] placeholder:text-[#555555] outline-none focus:border-[#7c3aed] w-24"
                      />
                    )}
                  </div>
                </div>

                {/* Summary */}
                {item.summary && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-medium text-[#555555] uppercase tracking-wide">Summary</span>
                      {item.summary_length && (
                        <span className="text-[10px] text-[#555555] bg-[#1f1f1f] border border-[#2a2a2a] px-1.5 py-0.5 rounded capitalize">
                          {item.summary_length}
                        </span>
                      )}
                    </div>
                    <div className="prose text-sm">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {item.summary}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                {/* Topics */}
                {item.topics && Object.keys(item.topics).length > 0 && (
                  <div>
                    <span className="text-xs font-medium text-[#555555] uppercase tracking-wide block mb-2">
                      Topics
                    </span>
                    <div className="space-y-2">
                      {Object.entries(item.topics).map(([topic, description]) => (
                        <div key={topic} className="p-2.5 bg-[#1f1f1f] rounded-lg border border-[#2a2a2a]">
                          <div className="text-xs font-medium text-[#a78bfa] mb-0.5">{topic}</div>
                          <div className="text-xs text-[#555555]">{description}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Error message */}
                {item.status === 'failed' && item.error_message && (
                  <div className="p-3 bg-[#ef4444]/10 border border-[#ef4444]/30 rounded-lg">
                    <p className="text-xs text-[#ef4444]">{item.error_message}</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
