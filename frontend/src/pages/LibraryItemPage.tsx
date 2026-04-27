import { useMemo, useState } from 'react'
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

export default function LibraryItemPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [showFullContent, setShowFullContent] = useState(false)

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

  return (
    <div className="artboard-root">
      <Sidebar active="library" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'Document']}
          actions={<button className="btn ghost" onClick={() => navigate('/library')}>Back to Library</button>}
        />
        <div className="page">
          <div style={{ maxWidth: 860, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
              <SourcePill type={sourceTypeDisplay} />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                ingested {metadataDate(item.ingested_at)}
              </span>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                published {metadataDate(item.published_at)}
              </span>
            </div>

            <h1 className="page-title" style={{ fontSize: 30 }}>{item.title}</h1>

            {(item.channel || item.author) && (
              <p className="page-subtitle" style={{ marginBottom: 18 }}>
                {(item.channel && item.author) ? `${item.channel} · ${item.author}` : item.channel || item.author}
              </p>
            )}

            {item.source_type === 'youtube' && (
              <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 20 }}>
                <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 10 }}>
                  YouTube metadata
                </div>
                {youtubeThumbnail && (
                  <img
                    src={youtubeThumbnail}
                    alt={item.title}
                    style={{ width: '100%', maxWidth: 440, aspectRatio: '16/9', objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 12 }}
                  />
                )}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: item.timestamps && Object.keys(item.timestamps).length > 0 ? 10 : 0 }}>
                  {item.channel && <span className="tag"><span className="dot" />channel: {item.channel}</span>}
                  {item.duration && <span className="tag"><span className="dot" />duration: {item.duration}</span>}
                  {item.views !== null && item.views !== undefined && <span className="tag"><span className="dot" />views: {item.views.toLocaleString()}</span>}
                  {item.subscribers && <span className="tag"><span className="dot" />subscribers: {item.subscribers}</span>}
                  {item.videos_count && <span className="tag"><span className="dot" />videos: {item.videos_count}</span>}
                  {item.detected_language && <span className="tag"><span className="dot" />language: {item.detected_language}</span>}
                </div>
                {item.timestamps && Object.keys(item.timestamps).length > 0 && (
                  <>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-subtle)', marginBottom: 6 }}>Timestamps</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {Object.entries(item.timestamps).slice(0, 8).map(([topic, time]) => (
                        <span key={`${topic}-${time}`} className="tag"><span className="dot" />{time} {topic}</span>
                      ))}
                    </div>
                  </>
                )}
              </div>
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
                  <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
                    <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 10 }}>
                      Full content
                    </div>
                    <DocumentMarkdown content={item.raw_content} />
                  </div>
                )}
              </div>
            )}

            {item.tags.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 10 }}>Tags</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {item.tags.map((tag) => (
                    <span key={tag} className="tag"><span className="dot" />{tag}</span>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', color: 'var(--text-subtle)', fontSize: 12 }}>
              {item.word_count !== null && <span className="mono">{item.word_count.toLocaleString()} words</span>}
              {item.summary_length && <span className="mono">summary: {item.summary_length}</span>}
              {item.llm_model && <span className="mono">model: {item.llm_model}</span>}
              <span className="mono">status: {item.status}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
