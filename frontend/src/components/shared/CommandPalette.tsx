import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchKnowledge } from '@/api/knowledge'
import Icons from './Icons'

const NAV_ITEMS = [
  { label: 'Today', icon: 'sparkle', to: '/today', hint: 'Home dashboard' },
  { label: 'Library', icon: 'library', to: '/library', hint: 'Browse all sources' },
  { label: 'Chat', icon: 'chat', to: '/chat', hint: 'Ask your library' },
  { label: 'Graph', icon: 'graph', to: '/graph', hint: 'Knowledge graph' },
  { label: 'Digest', icon: 'clock', to: '/digest', hint: 'Daily digest' },
  { label: 'YouTube', icon: 'yt', to: '/youtube', hint: 'Ingest YouTube video' },
  { label: 'Inbox', icon: 'inbox', to: '/inbox', hint: 'Processing queue' },
]

const IS_URL = /https?:\/\/|youtu|\.com\/|\.org\//

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const isUrl = IS_URL.test(query)

  const { data: searchData } = useQuery({
    queryKey: ['cmd-search', query],
    queryFn: () => fetchKnowledge({ per_page: 5, search: query }),
    enabled: open && query.trim().length > 1 && !isUrl,
    staleTime: 5000,
  })

  const searchItems = searchData?.items ?? []

  const filteredNav = query.trim()
    ? NAV_ITEMS.filter((n) => n.label.toLowerCase().includes(query.toLowerCase()) || n.hint.toLowerCase().includes(query.toLowerCase()))
    : NAV_ITEMS

  const allItems: Array<{ type: 'nav'; label: string; hint: string; to: string } | { type: 'item'; id: string; title: string; source_type: string } | { type: 'url'; label: string }> = [
    ...filteredNav.map((n) => ({ type: 'nav' as const, ...n })),
    ...searchItems.map((s) => ({ type: 'item' as const, id: s.id, title: s.title, source_type: s.source_type })),
    ...(isUrl ? [{ type: 'url' as const, label: `Ingest: ${query}` }] : []),
  ]

  const totalItems = allItems.length

  useEffect(() => {
    if (open) { setQuery(''); setSelected(0) }
  }, [open])

  useEffect(() => {
    setSelected(0)
  }, [query])

  const handleSelect = useCallback((item: typeof allItems[0]) => {
    onClose()
    if (item.type === 'nav') navigate(item.to)
    else if (item.type === 'item') navigate(`/library/${item.id}`)
    else if (item.type === 'url') navigate('/youtube', { state: { prefillUrl: query } })
  }, [navigate, onClose, query])

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, totalItems - 1)) }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)) }
      if (e.key === 'Enter') { e.preventDefault(); const item = allItems[selected]; if (item) handleSelect(item) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, selected, totalItems, allItems, handleSelect, onClose])

  if (!open) return null

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'grid', placeItems: 'start center', paddingTop: '15vh' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div style={{ width: '100%', maxWidth: 580, background: 'var(--bg-1)', border: '1px solid var(--border-strong)', borderRadius: 14, boxShadow: 'var(--shadow-lg)', overflow: 'hidden' }}>
        {/* Search input */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          <Icons.search style={{ width: 16, height: 16, color: 'var(--text-subtle)', flexShrink: 0 }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search or navigate…"
            style={{ flex: 1, background: 'transparent', border: 0, outline: 0, fontSize: 15, color: 'var(--text)', fontFamily: 'inherit' }}
          />
          <kbd style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-faint)', background: 'var(--bg-2)', padding: '2px 6px', borderRadius: 4 }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 380, overflowY: 'auto', padding: '6px 0' }}>
          {filteredNav.length > 0 && (
            <>
              <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-faint)', padding: '4px 16px 2px' }}>
                Navigate
              </div>
              {filteredNav.map((item, i) => {
                const Icon = Icons[item.icon as keyof typeof Icons]
                const isSelected = selected === i
                return (
                  <div
                    key={item.to}
                    onClick={() => handleSelect({ type: 'nav', ...item })}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 16px', cursor: 'pointer', background: isSelected ? 'var(--bg-active)' : 'transparent', transition: 'background 80ms' }}
                    onMouseEnter={() => setSelected(i)}
                  >
                    {Icon && <Icon style={{ width: 15, height: 15, color: 'var(--text-muted)', flexShrink: 0 }} />}
                    <span style={{ fontSize: 13.5, fontWeight: 500 }}>{item.label}</span>
                    <span style={{ fontSize: 12, color: 'var(--text-subtle)', marginLeft: 4 }}>{item.hint}</span>
                  </div>
                )
              })}
            </>
          )}

          {searchItems.length > 0 && (
            <>
              <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-faint)', padding: '8px 16px 2px' }}>
                Library
              </div>
              {searchItems.map((item, i) => {
                const idx = filteredNav.length + i
                const isSelected = selected === idx
                return (
                  <div
                    key={item.id}
                    onClick={() => handleSelect({ type: 'item', id: item.id, title: item.title, source_type: item.source_type })}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 16px', cursor: 'pointer', background: isSelected ? 'var(--bg-active)' : 'transparent' }}
                    onMouseEnter={() => setSelected(idx)}
                  >
                    {item.source_type === 'youtube'
                      ? <Icons.yt style={{ width: 15, height: 15, color: 'var(--text-subtle)', flexShrink: 0 }} />
                      : <Icons.paper style={{ width: 15, height: 15, color: 'var(--text-subtle)', flexShrink: 0 }} />}
                    <span style={{ fontSize: 13, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 1, overflow: 'hidden' } as React.CSSProperties}>
                      {item.title}
                    </span>
                  </div>
                )
              })}
            </>
          )}

          {isUrl && (
            <div
              onClick={() => handleSelect({ type: 'url', label: query })}
              style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 16px', cursor: 'pointer', background: selected === totalItems - 1 ? 'var(--bg-active)' : 'transparent' }}
              onMouseEnter={() => setSelected(totalItems - 1)}
            >
              <Icons.plus style={{ width: 15, height: 15, color: 'var(--accent)', flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: 'var(--accent)' }}>Ingest URL</span>
              <span style={{ fontSize: 12, color: 'var(--text-subtle)' }}>{query.slice(0, 60)}</span>
            </div>
          )}

          {allItems.length === 0 && (
            <div style={{ padding: '20px 16px', color: 'var(--text-subtle)', fontSize: 13.5, textAlign: 'center' }}>
              No results for "{query}"
            </div>
          )}
        </div>

        <div style={{ borderTop: '1px solid var(--border)', padding: '8px 16px', display: 'flex', gap: 16, fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
          <span>↑↓ navigate</span>
          <span>↵ select</span>
          <span>esc close</span>
        </div>
      </div>
    </div>
  )
}
