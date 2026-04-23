import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'

const comments = [
  { who: 'u/vault_hermit', ups: '412', time: '4h', text: 'SQLite + sqlite-vss for embeddings, Syncthing for device sync. Moved off Notion two years ago and never looked back.' },
  { who: 'u/markdown_maximalist', ups: '298', time: '3h', text: "Obsidian + Dataview + local Ollama for chat. The killer feature is chat *about your notes*, not just generic chat.", reply: true },
  { who: 'u/streamlit_refugee', ups: '187', time: '2h', text: 'Built a Streamlit app for this exact purpose. Worked for 6 months then I hit a wall — migrating to FastAPI + a proper frontend this month.' },
]

export default function RedditPage() {
  return (
    <div className="artboard-root">
      <Sidebar active="reddit" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'Reddit', 'r/PKMS discussion']}
          actions={
            <>
              <button className="btn ghost"><Icons.share /> Share</button>
              <button className="btn ghost"><Icons.tag /> Tag</button>
            </>
          }
        />
        <div className="page">
          <div style={{ maxWidth: 820, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <SourcePill type="reddit" />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>r/PKMS · 182 comments · posted 5h ago · ▲ 847</span>
            </div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 34, lineHeight: 1.1, margin: '0 0 8px', fontWeight: 700 }}>
              What setups are you running for a local-first second brain in 2026?
            </h1>
            <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>u/second_brain_curious · self-post</div>

            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 28 }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icons.sparkle style={{ width: 12, height: 12 }} /> Thread synthesis
              </div>
              <p style={{ fontSize: 15, lineHeight: 1.65, margin: '0 0 12px' }}>
                Thread consensus: <b>local SQLite + embedding index, synced via Syncthing.</b> Obsidian vaults still dominate, but a growing minority is rolling their own Streamlit/FastAPI frontends.
              </p>
              <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-muted)', margin: 0 }}>
                Contentious points: whether Notion counts as "local" (it doesn't, per the top 3 comments), and whether chunking strategy matters more than embedding model choice (split 60/40).
              </p>
            </div>

            <div style={{ background: 'var(--bg-1)', border: '1px dashed var(--border-accent)', borderRadius: 10, padding: '14px 16px', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Icons.sparkle style={{ width: 12, height: 12, color: 'var(--accent)' }} />
                <span className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-muted)' }}>Suggested tags</span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span className="tag accent"><span className="dot" />pkm <Icons.check style={{ width: 10, height: 10, marginLeft: 2 }} /></span>
                <span className="tag accent"><span className="dot" />local-first <Icons.check style={{ width: 10, height: 10, marginLeft: 2 }} /></span>
                {['+ sqlite', '+ embeddings', '+ obsidian'].map((t) => (
                  <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'transparent', border: '1px dashed var(--border-strong)', color: 'var(--text-muted)', cursor: 'pointer' }}>{t}</span>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12, marginBottom: 12 }}>
              <span style={{ flex: 1, fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                Top comments <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>by upvotes</span>
              </span>
              <button className="btn ghost" style={{ fontSize: 11 }}>Top ▾</button>
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              {comments.map((c, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, padding: 14, background: 'var(--bg-1)', border: '1px solid var(--border)', borderLeft: '2px solid var(--border-strong)', borderRadius: 8, marginLeft: c.reply ? 28 : 0 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, paddingTop: 2 }}>
                    <svg viewBox="0 0 12 12" style={{ width: 10, height: 10 }}><path d="M6 2 L10 8 L2 8 Z" fill="var(--accent)" /></svg>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>{c.ups}</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 500 }}>{c.who}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>· {c.time}</span>
                    </div>
                    <div style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.55 }}>{c.text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
