import client from './client'

export interface GraphSourceNode {
  id: string
  type: string
  label: string
  tags: string[]
  ingested_at: string | null
}

export interface GraphTagNode {
  id: string
  type: 'tag'
  label: string
  count: number
}

export type GraphNode = GraphSourceNode | GraphTagNode

export interface GraphEdge {
  source: string
  target: string
  type: 'item_tag' | 'tag_cooccurrence'
}

export async function fetchGraphNodes(): Promise<GraphNode[]> {
  const res = await client.get<{ nodes: GraphNode[] }>('/api/graph/nodes')
  return res.data.nodes
}

export async function fetchGraphEdges(): Promise<GraphEdge[]> {
  const res = await client.get<{ edges: GraphEdge[] }>('/api/graph/edges')
  return res.data.edges
}
