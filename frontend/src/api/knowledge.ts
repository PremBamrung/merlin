import client from './client'
import type { KnowledgeItem, PaginatedResponse, Tag } from '@/types'

export interface FetchKnowledgeParams {
  page?: number
  per_page?: number
  search?: string
  source_type?: string
  status?: string
  tags?: string
}

export async function fetchKnowledge(
  params: FetchKnowledgeParams = {}
): Promise<PaginatedResponse<KnowledgeItem>> {
  const p: Record<string, string | number> = {}
  if (params.page !== undefined) p.page = params.page
  if (params.per_page !== undefined) p.per_page = params.per_page
  if (params.search?.trim()) p.search = params.search.trim()
  if (params.source_type && params.source_type !== 'all') p.source_type = params.source_type
  if (params.status && params.status !== 'all') p.status = params.status
  if (params.tags?.trim()) p.tags = params.tags.trim()

  const res = await client.get<PaginatedResponse<KnowledgeItem>>('/api/knowledge', { params: p })
  return res.data
}

export async function fetchKnowledgeItem(id: string): Promise<KnowledgeItem> {
  const res = await client.get<KnowledgeItem>(`/api/knowledge/${id}`)
  return res.data
}

export async function deleteKnowledgeItem(id: string): Promise<void> {
  await client.delete(`/api/knowledge/${id}`)
}

export async function patchKnowledgeItem(id: string, updates: { tags?: string[]; title?: string }): Promise<KnowledgeItem> {
  const res = await client.patch<KnowledgeItem>(`/api/knowledge/${id}`, updates)
  return res.data
}

export async function fetchTags(): Promise<Tag[]> {
  const res = await client.get<Tag[]>('/api/tags')
  return res.data
}
