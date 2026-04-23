import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { fetchKnowledge, deleteKnowledgeItem } from '@/api/knowledge'
import type { KnowledgeItem } from '@/types'

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function LibraryPage() {
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [typeFilter, setTypeFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['knowledge', typeFilter, search],
    queryFn: () => fetchKnowledge({ per_page: 50, source_type: typeFilter, search }),
    staleTime: 30000,
    retry: 2,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteKnowledgeItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge'] }),
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0

  const sourceLabel = (type: string) =>
    type === 'youtube' ? 'youtube' : type === 'article' ? 'blog' : type

  return (
    <div className="artboard-root">
      <Sidebar active="library" />
      <div className="main">
        <Topbar crumbs={['Library']} />
        <div className="page">
          <div className="page-wide">
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 24 }}>
              <div>
                <h1 className="page-title">Library</h1>
                <p className="page-subtitle">
                  <span className="mono">{items.length}</span> of <span className="mono">{total}</span> sources
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: 260, padding: '8px 12px', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <Icons.search style={{ width: 14, height: 14, color: 'var(--text-subtle)' }} />
                  <input
                    placeholder="Search library…"
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && setSearch(searchInput)}
                    style={{ background: 'transparent', border: 0, outline: 0, color: 'var(--text)', flex: 1, fontSize: 13, fontFamily: 'inherit' }}
                  />
                  {searchInput && <span className="kbd" style={{ cursor: 'pointer' }} onClick={() => { setSearch(searchInput) }}>↵</span>}
                </div>
                <div style={{ display: 'flex', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 7, padding: 2 }}>
                  {(['grid', 'list'] as const).map((v) => (
                    <button key={v} onClick={() => setView(v)} style={{ background: view === v ? 'var(--bg-3)' : 'transparent', border: 0, padding: '5px 10px', borderRadius: 5, color: view === v ? 'var(--text)' : 'var(--text-muted)', cursor: 'pointer' }}>
                      {v === 'grid' ? <Icons.grid style={{ width: 13, height: 13 }} /> : <Icons.list style={{ width: 13, height: 13 }} />}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Filter chips */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'Everything' },
                { id: 'youtube', label: 'YouTube' },
                { id: 'article', label: 'Blogs' },
              ].map((f) => (
                <button
                  key={f.id}
                  onClick={() => setTypeFilter(f.id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', background: typeFilter === f.id ? 'var(--accent-soft)' : 'transparent', border: `1px solid ${typeFilter === f.id ? 'var(--border-accent)' : 'var(--border)'}`, borderRadius: 20, color: typeFilter === f.id ? 'var(--accent)' : 'var(--text-muted)', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit', transition: 'all var(--dur)' }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {isLoading && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, marginTop: 24 }}>
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                    <div style={{ aspectRatio: '16/9', background: 'var(--bg-2)' }} />
                    <div style={{ padding: 14 }}>
                      <div style={{ height: 12, background: 'var(--bg-2)', borderRadius: 4, marginBottom: 8 }} />
                      <div style={{ height: 10, background: 'var(--bg-2)', borderRadius: 4, width: '60%' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!isLoading && items.length === 0 && (
              <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--text-muted)' }}>
                <Icons.library style={{ width: 40, height: 40, margin: '0 auto 16px', display: 'block', opacity: 0.3 }} />
                <p style={{ fontSize: 16, margin: '0 0 8px' }}>No items in your library yet</p>
                <p style={{ fontSize: 13, margin: 0 }}>Ingest a YouTube video to get started</p>
              </div>
            )}

            {!isLoading && view === 'grid' && items.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, marginTop: 24 }}>
                {items.map((s: KnowledgeItem) => (
                  <div key={s.id} style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', cursor: 'pointer', transition: 'all var(--dur)', position: 'relative' }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-strong)')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                  >
                    <div style={{ position: 'relative', aspectRatio: '16/9', background: 'var(--bg-2)', overflow: 'hidden' }}>
                      {s.thumbnail_url ? (
                        <img src={s.thumbnail_url} alt={s.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <div style={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', color: 'var(--text-subtle)' }}>
                          {s.source_type === 'youtube' ? <Icons.yt style={{ width: 28, height: 28 }} /> : <Icons.paper style={{ width: 28, height: 28 }} />}
                        </div>
                      )}
                      {s.duration && (
                        <div style={{ position: 'absolute', bottom: 8, right: 8, background: 'rgba(0,0,0,0.7)', color: '#fff', padding: '2px 6px', borderRadius: 4, fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>
                          {s.duration}
                        </div>
                      )}
                    </div>
                    <div style={{ padding: 14 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <SourcePill type={sourceLabel(s.source_type)} />
                        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{timeAgo(s.ingested_at)}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(s.id) }}
                          style={{ marginLeft: 'auto', background: 'transparent', border: 0, cursor: 'pointer', color: 'var(--text-subtle)', padding: 2 }}
                          title="Delete"
                        >
                          <Icons.trash style={{ width: 12, height: 12 }} />
                        </button>
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.005em', marginBottom: 4, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' } as React.CSSProperties}>
                        {s.title}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginBottom: 8 }}>
                        {s.channel || s.author}
                      </div>
                      {s.summary && (
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 3, overflow: 'hidden' } as React.CSSProperties}>
                          {s.summary}
                        </div>
                      )}
                      {s.tags.length > 0 && (
                        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                          {s.tags.slice(0, 3).map((t) => (
                            <span key={t} className="tag"><span className="dot" />{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!isLoading && view === 'list' && items.length > 0 && (
              <div style={{ marginTop: 24, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
                {items.map((s: KnowledgeItem) => (
                  <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 16px', borderBottom: '1px solid var(--border)', cursor: 'pointer', transition: 'background var(--dur)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-1)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                  >
                    <SourcePill type={sourceLabel(s.source_type)} />
                    <span style={{ flex: 1, fontWeight: 500, fontSize: 13.5 }}>{s.title}</span>
                    <span style={{ color: 'var(--text-subtle)', fontSize: 12 }}>{s.channel || s.author}</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {s.tags.slice(0, 2).map((t) => (
                        <span key={t} className="tag" style={{ fontSize: 10 }}><span className="dot" />{t}</span>
                      ))}
                    </div>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', width: 60, textAlign: 'right' }}>{timeAgo(s.ingested_at)}</span>
                    <button onClick={() => deleteMutation.mutate(s.id)} style={{ background: 'transparent', border: 0, cursor: 'pointer', color: 'var(--text-subtle)', padding: 2 }}>
                      <Icons.trash style={{ width: 12, height: 12 }} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
