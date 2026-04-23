import { useState } from 'react'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'

const proposed = [
  { name: 'llm-research', existing: true, count: 34, color: '#c9a9ff', conf: 0.94 },
  { name: 'fundamentals', existing: true, count: 15, color: '#9ec9b8', conf: 0.87 },
  { name: 'rlhf', existing: false, conf: 0.82, reason: "new — you don't have a tag for this yet" },
  { name: 'karpathy', existing: false, conf: 0.78, reason: 'author/speaker tag' },
  { name: 'pytorch', existing: true, count: 12, color: '#b8a0ff', conf: 0.41, weak: true },
]

export default function IngestReviewPage() {
  const [selected, setSelected] = useState(new Set(['llm-research', 'rlhf', 'karpathy']))

  const toggle = (t: string) => {
    const next = new Set(selected)
    next.has(t) ? next.delete(t) : next.add(t)
    setSelected(next)
  }

  return (
    <div className="artboard-root">
      <Sidebar active="inbox" />
      <div className="main">
        <Topbar
          crumbs={['Inbox', 'Review ingestion']}
          actions={
            <>
              <button className="btn ghost">Skip</button>
              <button className="btn primary"><Icons.check /> Save to Library</button>
            </>
          }
        />
        <div className="page">
          <div style={{ maxWidth: 780, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <SourcePill type="youtube" />
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>ingested 2 minutes ago</span>
              <span className="tag accent" style={{ marginLeft: 'auto' }}><span className="dot" />ready to review</span>
            </div>
            <h1 className="page-title" style={{ fontSize: 30 }}>Andrej Karpathy: The State of GPT</h1>
            <p className="page-subtitle">Merlin has summarized this source and proposed tags + metadata. Adjust anything before saving to your Library.</p>

            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, marginBottom: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <span className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', flex: 1 }}>Summary</span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {['short', 'medium', 'long'].map((l) => (
                    <button key={l} className={`btn ghost${l === 'medium' ? ' is-active' : ''}`} style={{ fontSize: 11, padding: '3px 8px', ...(l === 'medium' ? { background: 'var(--bg-3)' } : {}) }}>{l}</button>
                  ))}
                </div>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-muted)', margin: 0 }}>
                A pragmatic tour of the full LLM training pipeline — from pretraining and instruction tuning to RLHF, plus when to use which model. Karpathy emphasizes treating LLMs as 'System 1' thinkers: fast, intuitive, and prone to mistakes when asked to reason in one shot.
              </p>
            </div>

            <div style={{ marginBottom: 24 }}>
              <div className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-subtle)', marginBottom: 12 }}>Proposed tags</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {proposed.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => toggle(t.name)}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                      fontFamily: 'inherit', border: '1px solid',
                      background: selected.has(t.name) ? 'var(--accent-soft)' : 'transparent',
                      borderColor: selected.has(t.name) ? 'var(--border-accent)' : 'var(--border)',
                      color: selected.has(t.name) ? 'var(--accent)' : 'var(--text-muted)',
                      opacity: t.weak ? 0.6 : 1,
                    }}
                  >
                    {t.existing && t.color && <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color }} />}
                    {t.name}
                    <span className="mono" style={{ fontSize: 10, opacity: 0.7 }}>{Math.round(t.conf * 100)}%</span>
                    {selected.has(t.name) && <Icons.check style={{ width: 10, height: 10 }} />}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
