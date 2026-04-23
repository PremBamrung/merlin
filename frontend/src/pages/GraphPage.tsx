import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import { useState } from 'react'

interface GraphNode {
  id: string; type: string; x: number; y: number; r?: number;
  color?: string; label: string; count?: number;
}

const nodes: GraphNode[] = [
  { id: 'llm-research', type: 'tag', x: 420, y: 260, r: 48, color: '#c9a9ff', label: 'llm-research', count: 34 },
  { id: 'rust', type: 'tag', x: 180, y: 180, r: 38, color: '#e8a87c', label: 'rust', count: 22 },
  { id: 'design-systems', type: 'tag', x: 660, y: 180, r: 34, color: '#8db089', label: 'design-systems', count: 18 },
  { id: 'pytorch', type: 'tag', x: 320, y: 400, r: 28, color: '#b8a0ff', label: 'pytorch', count: 12 },
  { id: 'mlops', type: 'tag', x: 540, y: 400, r: 24, color: '#a8c4e8', label: 'mlops', count: 8 },
  { id: 'fundamentals', type: 'tag', x: 460, y: 100, r: 26, color: '#9ec9b8', label: 'fundamentals', count: 15 },
  { id: 'woodworking', type: 'tag', x: 780, y: 360, r: 28, color: '#d99547', label: 'woodworking', count: 14 },
  { id: 'longevity', type: 'tag', x: 140, y: 380, r: 20, color: '#7ba2c9', label: 'longevity', count: 9 },
  { id: 'pkm', type: 'tag', x: 700, y: 80, r: 18, color: '#e8c47c', label: 'pkm', count: 6 },
  { id: 'v1', type: 'youtube', x: 380, y: 220, label: 'State of GPT' },
  { id: 'v2', type: 'youtube', x: 460, y: 300, label: 'nanoGPT' },
  { id: 'b1', type: 'blog', x: 500, y: 220, label: 'LLM Apps for Prod' },
  { id: 'b2', type: 'blog', x: 680, y: 220, label: 'Everyday colors' },
  { id: 'v3', type: 'youtube', x: 200, y: 220, label: 'Rust impatient' },
  { id: 'r1', type: 'reddit', x: 720, y: 120, label: 'PKM setups' },
]

const edges: [string, string][] = [
  ['v1', 'llm-research'], ['v1', 'fundamentals'],
  ['v2', 'llm-research'], ['v2', 'pytorch'],
  ['b1', 'llm-research'], ['b1', 'mlops'],
  ['b2', 'design-systems'],
  ['v3', 'rust'],
  ['r1', 'pkm'],
  ['llm-research', 'fundamentals'], ['llm-research', 'pytorch'], ['llm-research', 'mlops'],
]

const nodeMap = Object.fromEntries(nodes.map((n) => [n.id, n]))

export default function GraphPage() {
  const [, setHover] = useState<GraphNode | null>(null)

  return (
    <div className="artboard-root">
      <Sidebar active="graph" />
      <div className="main">
        <Topbar
          crumbs={['Graph']}
          actions={
            <>
              <button className="btn ghost"><Icons.filter /> Filter</button>
              <button className="btn ghost">2D</button>
            </>
          }
        />
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--bg)' }}>
            <svg viewBox="0 0 900 520" style={{ width: '100%', height: '100%', display: 'block' }}>
              <defs>
                <radialGradient id="glow">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </radialGradient>
              </defs>
              {edges.map(([a, b], i) => {
                const na = nodeMap[a], nb = nodeMap[b]
                if (!na || !nb) return null
                return <line key={i} x1={na.x} y1={na.y} x2={nb.x} y2={nb.y} stroke="var(--border-strong)" strokeWidth="0.8" strokeOpacity="0.6" />
              })}
              {nodes.filter((n) => n.type !== 'tag').map((n) => (
                <g key={n.id} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)} style={{ cursor: 'pointer' }}>
                  <circle cx={n.x} cy={n.y} r="5" fill="var(--bg-3)" stroke="var(--border-strong)" strokeWidth="1" />
                  <circle cx={n.x} cy={n.y} r="2.5" fill={n.type === 'youtube' ? '#e0826a' : n.type === 'blog' ? '#8db089' : '#d99547'} />
                </g>
              ))}
              {nodes.filter((n) => n.type === 'tag').map((n) => (
                <g key={n.id} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)} style={{ cursor: 'pointer' }}>
                  <circle cx={n.x} cy={n.y} r={(n.r || 20) + 20} fill="url(#glow)" opacity="0.4" />
                  <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity="0.08" stroke={n.color} strokeOpacity="0.5" strokeWidth="1" />
                  <text x={n.x} y={n.y - 4} textAnchor="middle" fill="var(--text)" fontSize="13" fontWeight="500" fontFamily="Inter">{n.label}</text>
                  <text x={n.x} y={n.y + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="10" fontFamily="JetBrains Mono">{n.count}</text>
                </g>
              ))}
            </svg>

            <div style={{ position: 'absolute', top: 16, left: 16, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>Legend</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--accent)', background: 'rgba(201,169,255,0.1)', display: 'inline-block' }} /> Tag</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#e0826a', display: 'inline-block' }} /> YouTube</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#8db089', display: 'inline-block' }} /> Blog</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d99547', display: 'inline-block' }} /> Reddit</div>
              </div>
            </div>
          </div>

          <div style={{ width: 300, borderLeft: '1px solid var(--border)', padding: 24, background: 'var(--bg-1)', overflowY: 'auto' }}>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>Cluster insight</div>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, lineHeight: 1.1, margin: '0 0 10px', fontWeight: 700 }}>
              Your LLM research is forming a spine.
            </h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 16 }}>
              34 sources across 5 connected tags. The densest bridges run through <b style={{ color: 'var(--text)' }}>fundamentals</b> and <b style={{ color: 'var(--text)' }}>pytorch</b>.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { type: 'GAP', color: 'var(--accent)', text: 'No sources tagged both rust and llm-research — worth exploring?' },
                { type: 'DENSE', color: 'var(--good)', text: 'The llm-research cluster is your most active — 7 sources this month.' },
                { type: 'STALE', color: 'var(--warn)', text: 'woodworking hasn\'t been touched in 47 days.' },
              ].map((r) => (
                <div key={r.type} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 12px', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)' }}>
                  <span className="mono" style={{ fontSize: 10.5, color: r.color }}>{r.type}</span>
                  <span>{r.text}</span>
                </div>
              ))}
            </div>
            <button className="btn" style={{ width: '100%', marginTop: 20, justifyContent: 'center' }}>
              <Icons.sparkle /> Ask about this cluster
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
