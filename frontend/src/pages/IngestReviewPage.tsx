import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { fetchKnowledgeItem, patchKnowledgeItem } from '@/api/knowledge'

export default function IngestReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [savedOk, setSavedOk] = useState(false)

  const { data: item, isLoading, isError } = useQuery({
    queryKey: ['knowledge', id],
    queryFn: () => fetchKnowledgeItem(id!),
    enabled: !!id,
  })

  useEffect(() => {
    if (item?.tags) setSelected(new Set(item.tags))
  }, [item?.tags?.join(',')])

  const saveMutation = useMutation({
    mutationFn: () => patchKnowledgeItem(id!, { tags: Array.from(selected) }),
    onSuccess: () => {
      setSavedOk(true)
      setTimeout(() => navigate('/library'), 1200)
    },
  })

  const toggle = (t: string) => {
    const next = new Set(selected)
    next.has(t) ? next.delete(t) : next.add(t)
    setSelected(next)
  }

  if (isLoading) {
    return (
      <div className="artboard-root">
        <Sidebar active="inbox" />
        <div className="main">
          <Topbar crumbs={['Inbox', 'Review']} />
          <div className="page" style={{ display: 'grid', placeItems: 'center' }}>
            <span style={{ color: 'var(--text-subtle)' }}>Loading…</span>
          </div>
        </div>
      </div>
    )
  }

  if (isError || !item) {
    return (
      <div className="artboard-root">
        <Sidebar active="inbox" />
        <div className="main">
          <Topbar crumbs={['Inbox', 'Review']} />
          <div className="page" style={{ display: 'grid', placeItems: 'center' }}>
            <span style={{ color: 'var(--danger)' }}>Item not found.</span>
          </div>
        </div>
      </div>
    )
  }

  const sourceTypeDisplay = item.source_type === 'article' ? 'blog' : item.source_type

  return (
    <div className="artboard-root">
      <Sidebar active="inbox" />
      <div className="main">
        <Topbar
          crumbs={['Inbox', 'Review ingestion']}
          actions={
            <>
              <button className="btn ghost" onClick={() => navigate('/inbox')}>Skip</button>
              <button
                className="btn primary"
                disabled={saveMutation.isPending || savedOk}
                onClick={() => saveMutation.mutate()}
              >
                <Icons.check /> {savedOk ? 'Saved!' : saveMutation.isPending ? 'Saving…' : 'Save to Library'}
              </button>
            </>
          }
        />
        <div className="page">
          <div style={{ maxWidth: 780, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <SourcePill type={sourceTypeDisplay} />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                ingested {item.ingested_at ? new Date(item.ingested_at).toLocaleString() : ''}
              </span>
              <span className="tag accent" style={{ marginLeft: 'auto' }}>
                <span className="dot" />ready to review
              </span>
            </div>
            <h1 className="page-title" style={{ fontSize: 30 }}>{item.title}</h1>
            {item.author && (
              <p className="page-subtitle" style={{ marginBottom: 8 }}>by {item.author}</p>
            )}
            <p className="page-subtitle">Merlin has summarized this source and proposed tags + metadata. Adjust anything before saving to your Library.</p>

            {item.summary && (
              <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', flex: 1 }}>Summary</span>
                  {item.summary_length && (
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{item.summary_length}</span>
                  )}
                </div>
                <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-muted)', margin: 0 }}>
                  {item.summary}
                </p>
              </div>
            )}

            {item.tags.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 12 }}>Tags</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {item.tags.map((t) => (
                    <button
                      key={t}
                      onClick={() => toggle(t)}
                      style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                        fontFamily: 'inherit', border: '1px solid',
                        background: selected.has(t) ? 'var(--accent-soft)' : 'transparent',
                        borderColor: selected.has(t) ? 'var(--border-accent)' : 'var(--border)',
                        color: selected.has(t) ? 'var(--accent)' : 'var(--text-muted)',
                      }}
                    >
                      {t}
                      {selected.has(t) && <Icons.check style={{ width: 10, height: 10 }} />}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {item.word_count && (
              <div style={{ display: 'flex', gap: 16, color: 'var(--text-subtle)', fontSize: 12 }}>
                <span className="mono">{item.word_count.toLocaleString()} words</span>
                {item.llm_model && <span className="mono">model: {item.llm_model}</span>}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
