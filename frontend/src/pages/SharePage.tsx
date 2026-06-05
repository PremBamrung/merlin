import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import DocumentMarkdown from '@/components/shared/DocumentMarkdown'
import { fetchKnowledge } from '@/api/knowledge'
import { createShare } from '@/api/share'

export default function SharePage() {
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showPanel, setShowPanel] = useState(false)

  const { data } = useQuery({
    queryKey: ['knowledge', { source_type: 'article', per_page: 1 }],
    queryFn: () => fetchKnowledge({ source_type: 'article', per_page: 1 }),
  })

  const item = data?.items?.[0]

  const shareMutation = useMutation({
    mutationFn: () => createShare(item!.id),
    onSuccess: (res) => {
      setShareUrl(window.location.origin + res.url)
      setShowPanel(true)
    },
  })

  const copyLink = () => {
    if (!shareUrl) return
    navigator.clipboard.writeText(shareUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!item) {
    return (
      <div className="artboard-root">
        <Sidebar active="blogs" />
        <div className="main">
          <Topbar crumbs={['Library', 'Share']} />
          <div className="page" style={{ display: 'grid', placeItems: 'center' }}>
            <div style={{ textAlign: 'center', color: 'var(--text-subtle)' }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>✦</div>
              <div>No articles in your library yet.</div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="artboard-root">
      <Sidebar active="blogs" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'Article', item.title.slice(0, 40) + (item.title.length > 40 ? '…' : '')]}
          actions={
            <>
              <button className="btn ghost" onClick={copyLink} disabled={!shareUrl}>
                <Icons.link /> {copied ? 'Copied!' : 'Copy link'}
              </button>
              <button
                className="btn primary"
                onClick={() => shareMutation.mutate()}
                disabled={shareMutation.isPending}
              >
                <Icons.share /> {shareMutation.isPending ? 'Generating…' : 'Share public'}
              </button>
            </>
          }
        />
        <div className="page" style={{ background: 'var(--bg)' }}>
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
              <SourcePill type="blog" />
              {item.author && (
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                  {item.author} · saved {item.ingested_at ? new Date(item.ingested_at).toLocaleDateString() : ''}
                </span>
              )}
            </div>

            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 44, lineHeight: 1.08, letterSpacing: '-0.015em', margin: '0 0 14px', fontWeight: 700 }}>
              {item.title}
            </h1>
            {item.author && (
              <div style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 28 }}>by {item.author}</div>
            )}

            {item.tags.length > 0 && (
              <div style={{ display: 'flex', gap: 6, marginBottom: 32 }}>
                {item.tags.map((t) => (
                  <span key={t} className="tag">
                    <span className="dot" />
                    {t}
                  </span>
                ))}
              </div>
            )}

            {item.summary && (
              <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 36, position: 'relative' }}>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icons.sparkle style={{ width: 12, height: 12 }} /> Merlin's summary
                </div>
                <div style={{ fontSize: 16, lineHeight: 1.7, color: 'var(--text)' }}>
                  <DocumentMarkdown content={item.summary} />
                </div>
              </div>
            )}

            {item.word_count && (
              <div style={{ color: 'var(--text-subtle)', fontSize: 12, marginBottom: 24 }} className="mono">
                {item.word_count.toLocaleString()} words
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Share panel */}
      {showPanel && shareUrl && (
        <div style={{ position: 'fixed', bottom: 0, right: 0, transform: 'translate(-32px, -32px)', width: 380, background: 'var(--bg-1)', border: '1px solid var(--border-accent)', borderRadius: 12, padding: 18, boxShadow: 'var(--shadow-lg)', zIndex: 100 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <Icons.share style={{ width: 16, height: 16, color: 'var(--accent)' }} />
            <span style={{ fontSize: 14, fontWeight: 600 }}>Share this summary</span>
            <button style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} onClick={() => setShowPanel(false)}>
              <Icons.close style={{ width: 14, height: 14, color: 'var(--text-subtle)' }} />
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 7 }}>
            <Icons.link style={{ width: 13, height: 13, color: 'var(--text-subtle)' }} />
            <span className="mono" style={{ fontSize: 11.5, flex: 1, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {shareUrl}
            </span>
            <button className="btn" style={{ padding: '4px 10px', fontSize: 11.5 }} onClick={copyLink}>
              {copied ? '✓' : 'Copy'}
            </button>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginTop: 10 }}>
            Public link — anyone with this URL can view the summary.
          </div>
        </div>
      )}
    </div>
  )
}
