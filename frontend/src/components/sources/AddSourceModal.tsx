import { useEffect, useRef } from 'react'
import { X, Youtube } from 'lucide-react'
import clsx from 'clsx'
import { useUIStore } from '@/stores/uiStore'
import YouTubeForm from './YouTubeForm'

export default function AddSourceModal() {
  const open = useUIStore((s) => s.addSourceOpen)
  const setOpen = useUIStore((s) => s.setAddSourceOpen)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && open) setOpen(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, setOpen])

  // Lock body scroll when open
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === overlayRef.current) setOpen(false)
      }}
    >
      <div
        className="relative w-full max-w-lg bg-[#161616] border border-[#2a2a2a] rounded-xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a2a]">
          <h2 className="text-[#e8e8e8] font-semibold text-base">
            Add to Knowledge Base
          </h2>
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 rounded-lg text-[#555555] hover:text-[#e8e8e8] hover:bg-[#2a2a2a] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Source type tabs */}
        <div className="flex gap-1 px-6 pt-4">
          {/* YouTube — active */}
          <button
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              'bg-[#7c3aed]/20 text-[#a78bfa] border border-[#7c3aed]/40'
            )}
          >
            <Youtube size={14} />
            YouTube
          </button>

          {/* Article — coming soon */}
          <button
            disabled
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-[#555555] cursor-not-allowed relative"
          >
            Article
            <span className="ml-1 px-1.5 py-0.5 bg-[#2a2a2a] text-[#555555] text-[10px] rounded-full font-medium">
              soon
            </span>
          </button>

          {/* PDF — coming soon */}
          <button
            disabled
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-[#555555] cursor-not-allowed"
          >
            PDF
            <span className="ml-1 px-1.5 py-0.5 bg-[#2a2a2a] text-[#555555] text-[10px] rounded-full font-medium">
              soon
            </span>
          </button>
        </div>

        {/* Form */}
        <div className="px-6 pb-6 pt-4">
          <YouTubeForm />
        </div>
      </div>
    </div>
  )
}
