import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { fetchDigest, ingestDigestItem, skipDigestItem } from '@/api/digest'

export default function DigestPage() {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['digest'],
    queryFn: () => fetchDigest(30),
    staleTime: 60000,
  })

  const ingestMutation = useMutation({
    mutationFn: ingestDigestItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['digest'] }),
  })

  const skipMutation = useMutation({
    mutationFn: skipDigestItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['digest'] }),
  })

  const sections = data?.sections ?? []
  const total = data?.total ?? 0

  return (
    <div className="artboard-root">
      <Sidebar active="digest" />
      <div className="main">
        <Topbar
          crumbs={['Digest', new Date().toLocaleDateString('en-US', { weekday: 'long' }) + ' morning']}
          actions={
            <>
              <button className="btn ghost"><Icons.settings /> Sources</button>
              <button className="btn ghost"><Icons.share /> Send to email</button>
            </>
          }
        />
        <div className="page">
          <div className="page-narrow">
            <div style={{ marginBottom: 28 }}>
              <div className="mono" style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-subtle)', marginBottom: 6 }}>
                {new Date().toLocaleDateString('en-US', { weekday: 'long' })} morning · {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
              </div>
              <h1 className="page-title">
                Your digest <span className="dim">— {total > 0 ? `${total} sources` : 'catching up'}.</span>
              </h1>
              <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '6px 0 0' }}>
                Your recently ingested sources, organized for review.{' '}
                <span className="text-accent" style={{ cursor: 'pointer' }}>Adjust what gets in →</span>
              </p>
            </div>

            <div className="digest-stats">
              {[
                [String(total), 'in library'],
                [String(sections.length), 'sections'],
              ].map(([k, l]) => (
                <div key={l}>
                  <div className="mono-k">{k}</div>
                  <div className="mono-l">{l}</div>
                </div>
              ))}
            </div>

            {isLoading && (
              <div style={{ color: 'var(--text-subtle)', padding: '24px 0', fontSize: 13.5 }}>Loading digest…</div>
            )}

            {!isLoading && sections.length === 0 && (
              <div style={{ color: 'var(--text-subtle)', padding: '40px 0', fontSize: 13.5, textAlign: 'center' }}>
                <div style={{ fontSize: 32, marginBottom: 10 }}>✦</div>
                <div>No sources yet — ingest some content to build your digest.</div>
              </div>
            )}

            {sections.map((sec) => (
              <div key={sec.title} style={{ marginTop: 28 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 22, margin: 0, fontWeight: 700 }}>{sec.title}</h2>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{sec.subtitle}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {sec.items.map((it) => (
                    <div key={it.id} className="digest-card">
                      <div className="digest-thumb">
                        {it.source_type === 'youtube' && <Icons.yt style={{ width: 22, height: 22 }} />}
                        {it.source_type === 'article' && <Icons.paper style={{ width: 22, height: 22 }} />}
                        {it.source_type === 'pdf' && <Icons.paper style={{ width: 22, height: 22 }} />}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                          <SourcePill type={it.source_type === 'article' ? 'blog' : it.source_type} />
                          {it.author && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{it.author}</span>}
                          {it.ingested_at && (
                            <span className="text-subtle mono" style={{ fontSize: 10.5 }}>
                              · {new Date(it.ingested_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 5, lineHeight: 1.3 }}>{it.title}</div>
                        {it.summary && (
                          <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 8 }}>{it.summary}</div>
                        )}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{it.why}</span>
                          <span className="match-bar"><span style={{ width: `${it.match_score * 100}%` }} /></span>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>{Math.round(it.match_score * 100)}%</span>
                          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                            <button
                              className="btn ghost"
                              style={{ fontSize: 11, padding: '3px 8px' }}
                              onClick={() => ingestMutation.mutate(it.id)}
                            >
                              Ingest
                            </button>
                            <button
                              className="btn ghost"
                              style={{ fontSize: 11, padding: '3px 8px' }}
                              onClick={() => skipMutation.mutate(it.id)}
                            >
                              Skip
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <style>{`
        .digest-stats {
          display: flex; align-items: center; gap: 20px;
          padding: 14px 18px; background: var(--bg-1);
          border: 1px solid var(--border); border-radius: 10px; margin-bottom: 12px;
        }
        .mono-k { font-family: var(--font-ui); font-size: 22px; font-weight: 700; line-height: 1; }
        .mono-l { font-size: 10.5px; color: var(--text-subtle); margin-top: 3px; text-transform: uppercase; letter-spacing: 0.1em; }
        .chip-sm {
          background: transparent; border: 1px solid var(--border);
          padding: 4px 10px; border-radius: 14px;
          color: var(--text-muted); font-size: 11px; cursor: pointer; font-family: inherit;
        }
        .chip-sm.active { background: var(--bg-3); color: var(--text); border-color: var(--border-strong); }
        .digest-card {
          display: flex; gap: 14px; padding: 14px;
          background: var(--bg-1); border: 1px solid var(--border); border-radius: 10px;
          transition: border-color var(--dur); cursor: pointer;
        }
        .digest-card:hover { border-color: var(--border-accent); }
        .digest-thumb {
          width: 48px; height: 48px; border-radius: 8px;
          background: var(--bg-2); display: grid; place-items: center;
          color: var(--text-muted); flex-shrink: 0;
        }
        .match-bar {
          width: 50px; height: 3px; background: var(--bg-3);
          border-radius: 2px; display: inline-block; overflow: hidden;
        }
        .match-bar > span { display: block; height: 100%; background: var(--accent); }
      `}</style>
    </div>
  )
}
