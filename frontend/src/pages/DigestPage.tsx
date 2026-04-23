import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'

const sections = [
  {
    title: 'From your trusted voices',
    subtitle: '4 new pieces · based on authors you follow',
    items: [
      { type: 'youtube', title: "Let's reproduce GPT-2 (124M)", author: 'Andrej Karpathy', meta: '4h ago · 2:14:18', why: 'You follow Karpathy · tag: llm-research', summary: 'A full four-hour build, from tokenizer to training loop.', match: 0.98 },
      { type: 'blog', title: 'Scaling laws revisited: what Chinchilla missed', author: 'Chip Huyen', meta: '1d ago · 14 min', why: 'You follow Huyen · tag: llm-research', summary: "A critical re-read of the compute-optimal frontier.", match: 0.94 },
      { type: 'youtube', title: 'Rust beyond the borrow checker', author: 'Jon Gjengset', meta: '2d ago · 58:22', why: 'You follow Jon · tag: rust', summary: "Deep dive on Rust's type system past the surface ownership story.", match: 0.88 },
    ],
  },
  {
    title: 'Recommended from YouTube',
    subtitle: '6 picks from your subscriptions · matched to your tags',
    items: [
      { type: 'youtube', title: 'The hidden cost of vector databases in production', author: 'LLMOps.io', meta: '3h ago · 22:04', why: 'Matches your tag: mlops · 3 similar sources in vault', summary: 'Benchmarks of Pinecone, Weaviate, Qdrant under realistic load.', match: 0.91 },
      { type: 'youtube', title: 'Why Obsidian is losing to plain markdown + git', author: 'No Boilerplate', meta: '1d ago · 14:08', why: 'Matches your tag: pkm · 6 similar sources', summary: 'A manifesto for stripping PKM back to files on disk.', match: 0.87 },
    ],
  },
  {
    title: 'From authors you might like',
    subtitle: '2 suggested voices · based on your library',
    items: [
      { type: 'blog', title: 'The Bitter Lesson, 10 years on', author: 'Sara Hooker', meta: 'new voice', why: "93% of your llm-research sources cite adjacent ideas", summary: "Hooker's retrospective on scaling dogma.", match: 0.82, isNew: true },
    ],
  },
]

export default function DigestPage() {
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
              <h1 className="page-title">Your digest <span className="dim">— 12 new things, curated.</span></h1>
              <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '6px 0 0' }}>
                Pulled from your trusted authors + YouTube subs, filtered against your tags.{' '}
                <span className="text-accent" style={{ cursor: 'pointer' }}>Adjust what gets in →</span>
              </p>
            </div>

            <div className="digest-stats">
              {[['12', 'picked'], ['47', 'scanned'], ['8', 'voices'], ['6', 'tags matched']].map(([k, l]) => (
                <div key={l}>
                  <div className="mono-k">{k}</div>
                  <div className="mono-l">{l}</div>
                </div>
              ))}
              <div style={{ height: 24, width: 1, background: 'var(--border)' }} />
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                <button className="chip-sm active">Today</button>
                <button className="chip-sm">Week</button>
                <button className="chip-sm">Archive</button>
              </div>
            </div>

            {sections.map((sec) => (
              <div key={sec.title} style={{ marginTop: 28 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 22, margin: 0, fontWeight: 700 }}>{sec.title}</h2>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{sec.subtitle}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {sec.items.map((it, i) => (
                    <div key={i} className="digest-card">
                      <div className="digest-thumb">
                        {it.type === 'youtube' && <Icons.yt style={{ width: 22, height: 22 }} />}
                        {it.type === 'blog' && <Icons.paper style={{ width: 22, height: 22 }} />}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                          <SourcePill type={it.type} />
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{it.author}</span>
                          <span className="text-subtle mono" style={{ fontSize: 10.5 }}>· {it.meta}</span>
                          {'isNew' in it && it.isNew && (
                            <span className="tag accent" style={{ marginLeft: 'auto', fontSize: 10 }}>
                              <span className="dot" />new voice
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 5, lineHeight: 1.3 }}>{it.title}</div>
                        <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 8 }}>{it.summary}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{it.why}</span>
                          <span className="match-bar"><span style={{ width: `${it.match * 100}%` }} /></span>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>{Math.round(it.match * 100)}%</span>
                          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                            <button className="btn ghost" style={{ fontSize: 11, padding: '3px 8px' }}>Ingest</button>
                            <button className="btn ghost" style={{ fontSize: 11, padding: '3px 8px' }}>Skip</button>
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
