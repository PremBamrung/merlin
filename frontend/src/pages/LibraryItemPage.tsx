import { useMemo, useState, useRef, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import SourcePill from '@/components/shared/SourcePill'
import DocumentMarkdown from '@/components/shared/DocumentMarkdown'
import { fetchKnowledgeItem } from '@/api/knowledge'

function sourceLabel(type: string): string {
  return type === 'article' ? 'blog' : type
}

function metadataDate(value: string | null | undefined): string {
  if (!value) return 'N/A'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleString()
}

function timestampToSeconds(ts: string): number {
  const parts = ts.split(':').map(Number)
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2]
  if (parts.length === 2) return parts[0] * 60 + parts[1]
  return 0
}

export default function LibraryItemPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [showFullContent, setShowFullContent] = useState(false)
  const transcriptRef = useRef<HTMLDivElement>(null)

  const { data: item, isLoading, isError } = useQuery({
    queryKey: ['knowledge', id],
    queryFn: () => fetchKnowledgeItem(id!),
    enabled: !!id,
  })

  const sourceTypeDisplay = useMemo(() => {
    if (!item) return ''
    return sourceLabel(item.source_type)
  }, [item])

  const youtubeThumbnail = useMemo(() => {
    if (!item || item.source_type !== 'youtube') return null
    return item.thumbnail_url || (item.source_id ? `https://img.youtube.com/vi/${item.source_id}/hqdefault.jpg` : null)
  }, [item])

  const topics = useMemo(() => {
    if (!item?.topics) return []
    return Object.entries(item.topics).map(([name, ts]) => ({ name, timestamp: ts, seconds: timestampToSeconds(ts) }))
  }, [item])

  // Keyboard shortcut: Escape → back
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') navigate(-1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  if (isLoading) {
    return (
      <div className="artboard-root">
        <Sidebar active="library" />
        <div className="main">
          <Topbar crumbs={['Library', 'Document']} />
          <div className="page" style={{ display: 'grid', placeItems: 'center' }}>
            <span style={{ color: 'var(--text-subtle)' }}>Loading document…</span>
          </div>
        </div>
      </div>
    )
  }

  if (isError || !item) {
    return (
      <div className="artboard-root">
        <Sidebar active="library" />
        <div className="main">
          <Topbar crumbs={['Library', 'Document']} />
          <div className="page" style={{ display: 'grid', placeItems: 'center', gap: 12 }}>
            <span style={{ color: 'var(--danger)' }}>Document not found.</span>
            <button className="btn ghost" onClick={() => navigate('/library')}>Back to Library</button>
          </div>
        </div>
      </div>
    )
  }

  const youtubeWatchUrl = item.source_type === 'youtube' && item.source_id
    ? `https://www.youtube.com/watch?v=${item.source_id}`
    : null

  return (
    <div className="artboard-root">
      <Sidebar active="library" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'Document']}
          actions={<button className="btn ghost" onClick={() => navigate('/library')}>Back to Library</button>}
        />
        <div className="page">
          <div className="lib-item-outer">
            <div className="lib-item-layout">
              {/* Main content column */}
              <div className="lib-item-content">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
                  <SourcePill type={sourceTypeDisplay} />
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                    ingested {metadataDate(item.ingested_at)}
                  </span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                    published {metadataDate(item.published_at)}
                  </span>
                </div>

                <h1 className="page-title" style={{ fontSize: 28 }}>{item.title}</h1>

                {(item.channel || item.author) && (
                  <p className="page-subtitle" style={{ marginBottom: 18 }}>
                    {(item.channel && item.author) ? `${item.channel} · ${item.author}` : item.channel || item.author}
                  </p>
                )}

                {item.summary && (
                  <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 20 }}>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 10 }}>
                      Summary
                    </div>
                    <DocumentMarkdown content={item.summary} />
                  </div>
                )}

                {!item.summary && (
                  <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 20, color: 'var(--text-muted)' }}>
                    No summary is available for this document.
                  </div>
                )}

                {item.raw_content && (
                  <div style={{ marginBottom: 20 }}>
                    <button
                      className="btn ghost"
                      onClick={() => setShowFullContent((v) => !v)}
                      style={{ marginBottom: showFullContent ? 10 : 0 }}
                    >
                      {showFullContent ? 'Hide full content' : 'Show full content'}
                    </button>
                    {showFullContent && (
                      <div ref={transcriptRef} style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
                        <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 10 }}>
                          Full content
                        </div>
                        <DocumentMarkdown content={item.raw_content} />
                      </div>
                    )}
                  </div>
                )}

                <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', color: 'var(--text-subtle)', fontSize: 12, marginTop: 8 }}>
                  {item.word_count !== null && <span className="mono">{item.word_count.toLocaleString()} words</span>}
                  {item.summary_length && <span className="mono">summary: {item.summary_length}</span>}
                  {item.llm_model && <span className="mono">model: {item.llm_model}</span>}
                  <span className="mono">status: {item.status}</span>
                </div>
              </div>

              {/* Metadata sidebar */}
              <div className="lib-item-meta">
                {/* Thumbnail */}
                {youtubeThumbnail && (
                  <div style={{ marginBottom: 16 }}>
                    <img
                      src={youtubeThumbnail}
                      alt={item.title}
                      style={{ width: '100%', aspectRatio: '16/9', objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)' }}
                    />
                    {youtubeWatchUrl && (
                      <a
                        href={youtubeWatchUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ display: 'block', marginTop: 8, fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}
                      >
                        Watch on YouTube →
                      </a>
                    )}
                  </div>
                )}

                {/* YouTube metadata fields */}
                {item.source_type === 'youtube' && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 8 }}>
                      Details
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {item.channel && <div style={{ fontSize: 12.5 }}><span style={{ color: 'var(--text-subtle)' }}>Channel: </span>{item.channel}</div>}
                      {item.duration && <div style={{ fontSize: 12.5 }}><span style={{ color: 'var(--text-subtle)' }}>Duration: </span>{item.duration}</div>}
                      {item.views !== null && item.views !== undefined && <div style={{ fontSize: 12.5 }}><span style={{ color: 'var(--text-subtle)' }}>Views: </span>{item.views.toLocaleString()}</div>}
                      {item.subscribers && <div style={{ fontSize: 12.5 }}><span style={{ color: 'var(--text-subtle)' }}>Subscribers: </span>{item.subscribers}</div>}
                      {item.detected_language && <div style={{ fontSize: 12.5 }}><span style={{ color: 'var(--text-subtle)' }}>Language: </span>{item.detected_language}</div>}
                    </div>
                  </div>
                )}

                {/* Topic navigation */}
                {topics.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 8 }}>
                      Topics
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      {topics.map(({ name, timestamp, seconds }) => (
                        <div
                          key={name}
                          style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '5px 8px', borderRadius: 6, cursor: 'pointer', transition: 'background var(--dur)' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          onClick={() => {
                            if (youtubeWatchUrl) {
                              window.open(`${youtubeWatchUrl}&t=${seconds}`, '_blank', 'noopener,noreferrer')
                            } else if (showFullContent && transcriptRef.current) {
                              transcriptRef.current.scrollIntoView({ behavior: 'smooth' })
                            } else {
                              setShowFullContent(true)
                            }
                          }}
                          title={youtubeWatchUrl ? `Watch at ${timestamp} on YouTube` : `Jump to ${timestamp}`}
                        >
                          <span className="mono" style={{ fontSize: 10, color: 'var(--accent)', flexShrink: 0, minWidth: 44 }}>{timestamp}</span>
                          <span style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.3 }}>{name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tags */}
                {item.tags.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 8 }}>
                      Tags
                    </div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {item.tags.map((tag) => (
                        <span key={tag} className="tag" style={{ cursor: 'pointer' }} onClick={() => navigate(`/library?tag=${encodeURIComponent(tag)}`)} title={`Browse ${tag}`}>
                          <span className="dot" />{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .lib-item-outer { max-width: 1400px; margin: 0 auto; }
        .lib-item-layout { display: grid; grid-template-columns: 1fr; gap: 28px; }
        .lib-item-meta { order: -1; }
        @media (min-width: 1100px) {
          .lib-item-layout { grid-template-columns: 2fr 1fr; align-items: start; }
          .lib-item-meta { order: 0; position: sticky; top: 20px; }
        }
      `}</style>
    </div>
  )
}
