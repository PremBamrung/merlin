import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { BLOGS, TAGS } from '@/data/mockData'

export default function SharePage() {
  const b = BLOGS[0]

  return (
    <div className="artboard-root">
      <Sidebar active="blogs" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'Blog', b.title.slice(0, 40) + '…']}
          actions={
            <>
              <button className="btn ghost"><Icons.link /> Copy link</button>
              <button className="btn primary"><Icons.share /> Share public</button>
            </>
          }
        />
        <div className="page" style={{ background: 'var(--bg)' }}>
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
              <SourcePill type="blog" />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{b.site} · {b.readTime} · saved {b.added}</span>
            </div>

            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 44, lineHeight: 1.08, letterSpacing: '-0.015em', margin: '0 0 14px', fontWeight: 700 }}>
              {b.title}
            </h1>
            <div style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 28 }}>by {b.author}</div>

            <div style={{ display: 'flex', gap: 6, marginBottom: 32 }}>
              {b.tags.map((t) => (
                <span key={t} className="tag">
                  <span className="dot" style={{ background: TAGS.find((x) => x.name === t)?.color || '#999' }} />
                  {t}
                </span>
              ))}
            </div>

            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, marginBottom: 36, position: 'relative' }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Icons.sparkle style={{ width: 12, height: 12 }} /> Merlin's summary
              </div>
              <p style={{ fontSize: 16, lineHeight: 1.7, margin: '0 0 16px', color: 'var(--text)' }}>{b.summary}</p>
              <p style={{ fontSize: 14.5, lineHeight: 1.7, margin: 0, color: 'var(--text-muted)' }}>
                Huyen's central argument is that "prompt engineering" underestimates the operational work — evals are where most projects fail quietly.
              </p>
            </div>

            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, margin: '0 0 12px', fontWeight: 700 }}>Key points</h3>
            <ol style={{ fontSize: 14.5, lineHeight: 1.75, color: 'var(--text-muted)', paddingLeft: 20, margin: '0 0 32px' }}>
              <li><b style={{ color: 'var(--text)' }}>Evals are the hard part.</b> Prompts are easy; deciding if the new prompt is better is where time goes.</li>
              <li><b style={{ color: 'var(--text)' }}>Your vector DB is not a moat.</b> Retrieval quality is dominated by chunking and query rewrites.</li>
              <li><b style={{ color: 'var(--text)' }}>Cost is a latent design constraint.</b> Model choice reshapes your product, not just your bill.</li>
              <li><b style={{ color: 'var(--text)' }}>Prompt drift is real.</b> Version prompts like code; test against golden sets.</li>
            </ol>

            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, margin: '0 0 12px', fontWeight: 700 }}>Related in your vault</h3>
            <div style={{ display: 'grid', gap: 8, marginBottom: 40 }}>
              {[
                { type: 'youtube', t: 'State of GPT — Karpathy', why: 'Also in llm-research · shares RLHF discussion' },
                { type: 'reddit', t: "r/LocalLLaMA — DPO vs RLHF showdown", why: "Extends Huyen's DPO argument" },
              ].map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-1)', cursor: 'pointer', transition: 'border-color var(--dur)' }}>
                  <SourcePill type={r.type} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>{r.t}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-subtle)' }}>{r.why}</div>
                  </div>
                  <Icons.arrowUp style={{ width: 12, height: 12, transform: 'rotate(45deg)', color: 'var(--text-subtle)' }} />
                </div>
              ))}
            </div>

            {/* Share panel */}
            <div style={{ position: 'fixed', bottom: 0, right: 0, transform: 'translate(-32px, -32px)', width: 380, background: 'var(--bg-1)', border: '1px solid var(--border-accent)', borderRadius: 12, padding: 18, boxShadow: 'var(--shadow-lg)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <Icons.share style={{ width: 16, height: 16, color: 'var(--accent)' }} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>Share this summary</span>
                <Icons.close style={{ width: 14, height: 14, marginLeft: 'auto', cursor: 'pointer', color: 'var(--text-subtle)' }} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 7 }}>
                <Icons.link style={{ width: 13, height: 13, color: 'var(--text-subtle)' }} />
                <span className="mono" style={{ fontSize: 11.5, flex: 1, color: 'var(--text-muted)' }}>merlin.vault/s/xk2p-huyen-llm</span>
                <button className="btn" style={{ padding: '4px 10px', fontSize: 11.5 }}>Copy</button>
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 16, fontSize: 12 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <span style={{ width: 14, height: 14, border: '1px solid var(--border-strong)', borderRadius: 3, display: 'inline-grid', placeItems: 'center', background: 'var(--accent)', borderColor: 'var(--accent)', color: 'var(--bg)' }}>
                    <Icons.check style={{ width: 9, height: 9 }} />
                  </span>
                  Include tags
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <span style={{ width: 14, height: 14, border: '1px solid var(--border-strong)', borderRadius: 3, display: 'inline-block' }} />
                  Show related
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', marginLeft: 'auto' }}>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>expires</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text)' }}>7 days</span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
