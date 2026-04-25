import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import { fetchGraphNodes, fetchGraphEdges } from '@/api/graph'
import type { GraphNode } from '@/api/graph'

const SOURCE_COLORS: Record<string, string> = {
  youtube: '#e0826a',
  article: '#8db089',
  blog: '#8db089',
  reddit: '#d99547',
  pdf: '#a8c4e8',
}

const TAG_COLORS = [
  '#c9a9ff', '#e8a87c', '#8db089', '#b8a0ff', '#a8c4e8',
  '#9ec9b8', '#d99547', '#7ba2c9', '#e8c47c', '#f0a0b0',
]

function layoutNodes(nodes: GraphNode[], W = 900, H = 520) {
  const tags = nodes.filter((n) => n.type === 'tag') as Extract<GraphNode, { type: 'tag' }>[]
  const sources = nodes.filter((n) => n.type !== 'tag')

  const cx = W / 2, cy = H / 2
  const tagR = Math.min(W, H) * 0.35

  const positioned = new Map<string, { x: number; y: number; r?: number; color?: string }>()

  tags.forEach((t, i) => {
    const angle = (2 * Math.PI * i) / Math.max(tags.length, 1) - Math.PI / 2
    const r = 20 + Math.sqrt(t.count) * 6
    positioned.set(t.id, {
      x: cx + Math.cos(angle) * tagR,
      y: cy + Math.sin(angle) * tagR,
      r,
      color: TAG_COLORS[i % TAG_COLORS.length],
    })
  })

  sources.forEach((s, i) => {
    const srcNode = s as Extract<GraphNode, { tags: string[] }>
    const primaryTag = srcNode.tags?.[0] ? `tag:${srcNode.tags[0]}` : null
    const tagPos = primaryTag ? positioned.get(primaryTag) : null
    const angle = (2 * Math.PI * i) / Math.max(sources.length, 1)
    const spread = 50
    positioned.set(s.id, {
      x: tagPos ? tagPos.x + Math.cos(angle) * spread : cx + Math.cos(angle) * (tagR * 0.5),
      y: tagPos ? tagPos.y + Math.sin(angle) * spread : cy + Math.sin(angle) * (tagR * 0.5),
    })
  })

  return positioned
}

export default function GraphPage() {
  const [hovered, setHovered] = useState<GraphNode | null>(null)

  const { data: nodes = [], isLoading: nodesLoading } = useQuery({
    queryKey: ['graph', 'nodes'],
    queryFn: fetchGraphNodes,
    staleTime: 60000,
  })

  const { data: edges = [] } = useQuery({
    queryKey: ['graph', 'edges'],
    queryFn: fetchGraphEdges,
    staleTime: 60000,
  })

  const positions = useMemo(() => layoutNodes(nodes), [nodes])
  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const tags = nodes.filter((n) => n.type === 'tag') as Extract<GraphNode, { type: 'tag' }>[]
  const sources = nodes.filter((n) => n.type !== 'tag')
  const topTag = tags[0]

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
            {nodesLoading && (
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--text-subtle)' }}>
                Loading graph…
              </div>
            )}
            {!nodesLoading && nodes.length === 0 && (
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--text-subtle)', flexDirection: 'column', gap: 8 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>✦</div>
                  <div>No sources yet — ingest something to see the graph.</div>
                </div>
              </div>
            )}
            <svg viewBox="0 0 900 520" style={{ width: '100%', height: '100%', display: 'block' }}>
              <defs>
                <radialGradient id="glow">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </radialGradient>
              </defs>

              {edges.map((e, i) => {
                const a = positions.get(e.source), b = positions.get(e.target)
                if (!a || !b) return null
                return (
                  <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke="var(--border-strong)" strokeWidth={e.type === 'tag_cooccurrence' ? 0.4 : 0.8}
                    strokeOpacity={e.type === 'tag_cooccurrence' ? 0.3 : 0.6}
                  />
                )
              })}

              {sources.map((n) => {
                const pos = positions.get(n.id)
                if (!pos) return null
                const color = SOURCE_COLORS[n.type] ?? '#aaa'
                return (
                  <g key={n.id} onMouseEnter={() => setHovered(n)} onMouseLeave={() => setHovered(null)} style={{ cursor: 'pointer' }}>
                    <circle cx={pos.x} cy={pos.y} r="5" fill="var(--bg-3)" stroke="var(--border-strong)" strokeWidth="1" />
                    <circle cx={pos.x} cy={pos.y} r="2.5" fill={color} />
                  </g>
                )
              })}

              {tags.map((n, i) => {
                const pos = positions.get(n.id)
                if (!pos) return null
                const color = TAG_COLORS[i % TAG_COLORS.length]
                return (
                  <g key={n.id} onMouseEnter={() => setHovered(n)} onMouseLeave={() => setHovered(null)} style={{ cursor: 'pointer' }}>
                    <circle cx={pos.x} cy={pos.y} r={(pos.r || 20) + 20} fill="url(#glow)" opacity="0.4" />
                    <circle cx={pos.x} cy={pos.y} r={pos.r} fill={color} fillOpacity="0.08" stroke={color} strokeOpacity="0.5" strokeWidth="1" />
                    <text x={pos.x} y={pos.y - 4} textAnchor="middle" fill="var(--text)" fontSize="13" fontWeight="500" fontFamily="Inter">{n.label}</text>
                    <text x={pos.x} y={pos.y + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="10" fontFamily="JetBrains Mono">{n.count}</text>
                  </g>
                )
              })}
            </svg>

            <div style={{ position: 'absolute', top: 16, left: 16, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>Legend</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--accent)', background: 'rgba(201,169,255,0.1)', display: 'inline-block' }} /> Tag</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#e0826a', display: 'inline-block' }} /> YouTube</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#8db089', display: 'inline-block' }} /> Blog / Article</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#d99547', display: 'inline-block' }} /> Reddit</div>
              </div>
            </div>
          </div>

          <div style={{ width: 300, borderLeft: '1px solid var(--border)', padding: 24, background: 'var(--bg-1)', overflowY: 'auto' }}>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 10 }}>Overview</div>
            {hovered ? (
              <>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 20, lineHeight: 1.1, margin: '0 0 8px', fontWeight: 700 }}>
                  {hovered.label}
                </h3>
                {'count' in hovered && (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                    {hovered.count} source{hovered.count !== 1 ? 's' : ''} tagged with <b>{hovered.label}</b>
                  </p>
                )}
                {'tags' in hovered && (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                    {(hovered as Extract<GraphNode, { tags: string[] }>).tags.map((t) => (
                      <span key={t} className="tag"><span className="dot" />{t}</span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <h3 style={{ fontFamily: 'var(--font-display)', fontSize: 22, lineHeight: 1.1, margin: '0 0 10px', fontWeight: 700 }}>
                  {tags.length > 0 ? `${tags.length} tags · ${sources.length} sources` : 'Your knowledge graph'}
                </h3>
                {topTag && (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 16 }}>
                    Most connected tag: <b style={{ color: 'var(--text)' }}>{topTag.label}</b> ({topTag.count} sources)
                  </p>
                )}
                {nodes.length === 0 && !nodesLoading && (
                  <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>
                    Ingest your first source to start building your knowledge graph.
                  </p>
                )}
              </>
            )}
            <button className="btn" style={{ width: '100%', marginTop: 20, justifyContent: 'center' }} onClick={() => {}}>
              <Icons.sparkle /> Ask about this cluster
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
