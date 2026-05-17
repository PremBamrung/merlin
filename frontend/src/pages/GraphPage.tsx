import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as d3force from 'd3-force'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import { fetchGraphNodes, fetchGraphEdges } from '@/api/graph'
import type { GraphNode, GraphEdge } from '@/api/graph'

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

interface SimNode extends d3force.SimulationNodeDatum {
  id: string
  node: GraphNode
  r: number
  color: string
}

interface SimLink extends d3force.SimulationLinkDatum<SimNode> {
  edge: GraphEdge
}

export default function GraphPage() {
  const navigate = useNavigate()
  const [hovered, setHovered] = useState<GraphNode | null>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null)
  const [simNodes, setSimNodes] = useState<SimNode[]>([])
  const [simLinks, setSimLinks] = useState<SimLink[]>([])
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 })
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [dims, setDims] = useState({ w: 900, h: 520 })
  const simRef = useRef<d3force.Simulation<SimNode, SimLink> | null>(null)
  const dragging = useRef(false)
  const dragStart = useRef({ x: 0, y: 0, tx: 0, ty: 0 })

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

  // Track container size
  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      if (width > 0 && height > 0) setDims({ w: width, h: height })
    })
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  // Build and run simulation
  useEffect(() => {
    if (nodes.length === 0) return

    const tagNodes = nodes.filter((n) => n.type === 'tag') as Extract<GraphNode, { type: 'tag' }>[]
    const tagColorMap = new Map(tagNodes.map((t, i) => [t.id, TAG_COLORS[i % TAG_COLORS.length]]))

    const sNodes: SimNode[] = nodes.map((n) => {
      const isTag = n.type === 'tag'
      const tagNode = n as Extract<GraphNode, { type: 'tag' }>
      const r = isTag ? (20 + Math.sqrt(tagNode.count ?? 1) * 6) : 5
      const color = isTag
        ? (tagColorMap.get(n.id) ?? '#c9a9ff')
        : (SOURCE_COLORS[n.type] ?? '#aaa')
      return {
        id: n.id,
        node: n,
        r,
        color,
        x: dims.w / 2 + (Math.random() - 0.5) * 200,
        y: dims.h / 2 + (Math.random() - 0.5) * 200,
      }
    })

    const nodeById = new Map(sNodes.map((n) => [n.id, n]))

    const sLinks: SimLink[] = edges
      .filter((e) => nodeById.has(e.source) && nodeById.has(e.target))
      .map((e) => ({ source: nodeById.get(e.source)!, target: nodeById.get(e.target)!, edge: e }))

    const scale = Math.sqrt(dims.w / 900)
    const sim = d3force.forceSimulation<SimNode, SimLink>(sNodes)
      .force('link', d3force.forceLink<SimNode, SimLink>(sLinks).id((d) => d.id).distance(80 * scale).strength(0.3))
      .force('charge', d3force.forceManyBody<SimNode>().strength((d) => d.node.type === 'tag' ? -300 * scale : -80 * scale))
      .force('center', d3force.forceCenter(dims.w / 2, dims.h / 2))
      .force('collide', d3force.forceCollide<SimNode>((d) => (d.r + 8) * scale))
      .alphaDecay(0.02)

    sim.on('tick', () => {
      setSimNodes([...sNodes])
      setSimLinks([...sLinks])
    })

    simRef.current = sim
    return () => { sim.stop() }
  }, [nodes, edges, dims.w, dims.h])

  // Zoom on wheel
  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    setTransform((prev) => {
      const factor = e.deltaY < 0 ? 1.1 : 0.91
      const newScale = Math.max(0.2, Math.min(5, prev.scale * factor))
      return { ...prev, scale: newScale }
    })
  }, [])

  // Pan on drag
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as SVGElement).closest('[data-node]')) return
    dragging.current = true
    dragStart.current = { x: e.clientX, y: e.clientY, tx: transform.x, ty: transform.y }
  }, [transform])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return
    setTransform((prev) => ({
      ...prev,
      x: dragStart.current.tx + e.clientX - dragStart.current.x,
      y: dragStart.current.ty + e.clientY - dragStart.current.y,
    }))
  }, [])

  const onMouseUp = useCallback(() => { dragging.current = false }, [])

  const tags = nodes.filter((n) => n.type === 'tag') as Extract<GraphNode, { type: 'tag' }>[]
  const sources = nodes.filter((n) => n.type !== 'tag')
  const topTag = tags[0]

  const nodeById = useMemo(() => new Map(simNodes.map((n) => [n.id, n])), [simNodes])

  return (
    <div className="artboard-root">
      <Sidebar active="graph" />
      <div className="main">
        <Topbar
          crumbs={['Graph']}
          actions={
            <>
              <button className="btn ghost" onClick={() => setTransform({ x: 0, y: 0, scale: 1 })}>Reset view</button>
              <button className="btn ghost">2D</button>
            </>
          }
        />
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <div
            ref={containerRef}
            style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--bg)', cursor: dragging.current ? 'grabbing' : 'grab' }}
            onWheel={onWheel}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
          >
            {nodesLoading && (
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--text-subtle)' }}>
                Loading graph…
              </div>
            )}
            {!nodesLoading && nodes.length === 0 && (
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--text-subtle)' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>✦</div>
                  <div>No sources yet — ingest something to see the graph.</div>
                </div>
              </div>
            )}

            <svg
              ref={svgRef}
              style={{ width: '100%', height: '100%', display: 'block' }}
            >
              <defs>
                <radialGradient id="glow">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </radialGradient>
              </defs>

              <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>
                {/* Edges */}
                {simLinks.map((link, i) => {
                  const a = nodeById.get(typeof link.source === 'string' ? link.source : (link.source as SimNode).id)
                  const b = nodeById.get(typeof link.target === 'string' ? link.target : (link.target as SimNode).id)
                  if (!a || !b || a.x == null || a.y == null || b.x == null || b.y == null) return null
                  return (
                    <line key={i}
                      x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                      stroke="var(--border-strong)"
                      strokeWidth={link.edge.type === 'tag_cooccurrence' ? 0.4 : 0.8}
                      strokeOpacity={link.edge.type === 'tag_cooccurrence' ? 0.3 : 0.6}
                    />
                  )
                })}

                {/* Source nodes */}
                {simNodes.filter((n) => n.node.type !== 'tag').map((n) => {
                  if (n.x == null || n.y == null) return null
                  return (
                    <g key={n.id} data-node="1"
                      onMouseEnter={(e) => { setHovered(n.node); setTooltip({ x: e.clientX, y: e.clientY }) }}
                      onMouseMove={(e) => setTooltip({ x: e.clientX, y: e.clientY })}
                      onMouseLeave={() => { setHovered(null); setTooltip(null) }}
                      onClick={() => navigate(`/library/${n.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <circle cx={n.x} cy={n.y} r={n.r + 3} fill="var(--bg-3)" stroke="var(--border-strong)" strokeWidth="1" />
                      <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} />
                    </g>
                  )
                })}

                {/* Tag nodes */}
                {simNodes.filter((n) => n.node.type === 'tag').map((n) => {
                  if (n.x == null || n.y == null) return null
                  const tagNode = n.node as Extract<GraphNode, { type: 'tag' }>
                  return (
                    <g key={n.id} data-node="1"
                      onMouseEnter={(e) => { setHovered(n.node); setTooltip({ x: e.clientX, y: e.clientY }) }}
                      onMouseMove={(e) => setTooltip({ x: e.clientX, y: e.clientY })}
                      onMouseLeave={() => { setHovered(null); setTooltip(null) }}
                      onClick={() => navigate(`/library?tag=${encodeURIComponent(tagNode.label)}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <circle cx={n.x} cy={n.y} r={n.r + 20} fill="url(#glow)" opacity="0.4" />
                      <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} fillOpacity="0.08" stroke={n.color} strokeOpacity="0.5" strokeWidth="1" />
                      <text x={n.x} y={(n.y ?? 0) - 4} textAnchor="middle" fill="var(--text)" fontSize="13" fontWeight="500" fontFamily="Inter">{tagNode.label}</text>
                      <text x={n.x} y={(n.y ?? 0) + 12} textAnchor="middle" fill="var(--text-muted)" fontSize="10" fontFamily="JetBrains Mono">{tagNode.count}</text>
                    </g>
                  )
                })}
              </g>
            </svg>

            {/* Legend */}
            <div style={{ position: 'absolute', top: 16, left: 16, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>Legend</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 10, height: 10, borderRadius: '50%', border: '1px solid var(--accent)', background: 'rgba(201,169,255,0.1)', display: 'inline-block' }} /> Tag</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#e0826a', display: 'inline-block' }} /> YouTube</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: '#8db089', display: 'inline-block' }} /> Blog / Article</div>
              </div>
            </div>

            {/* Zoom hints */}
            <div style={{ position: 'absolute', bottom: 16, right: 16, fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--font-mono)' }}>
              scroll to zoom · drag to pan
            </div>

            {/* Hover tooltip */}
            {hovered && tooltip && (
              <div style={{
                position: 'fixed', left: tooltip.x + 12, top: tooltip.y - 8,
                background: 'var(--bg-3)', border: '1px solid var(--border-strong)',
                borderRadius: 8, padding: '8px 12px', fontSize: 12.5, pointerEvents: 'none',
                maxWidth: 220, boxShadow: 'var(--shadow)',
                zIndex: 100,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>{hovered.label}</div>
                {'count' in hovered && <div style={{ color: 'var(--text-muted)' }}>{hovered.count} source{hovered.count !== 1 ? 's' : ''}</div>}
                {'tags' in hovered && (hovered as Extract<GraphNode, { tags: string[] }>).tags.length > 0 && (
                  <div style={{ color: 'var(--text-subtle)', marginTop: 4 }}>
                    {(hovered as Extract<GraphNode, { tags: string[] }>).tags.slice(0, 3).join(', ')}
                  </div>
                )}
              </div>
            )}
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
            <button className="btn" style={{ width: '100%', marginTop: 20, justifyContent: 'center' }} onClick={() => navigate('/chat')}>
              <Icons.sparkle /> Ask about this cluster
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
