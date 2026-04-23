import client from './client'
import type { KnowledgeItem, PaginatedResponse } from '@/types'

export interface FetchKnowledgeParams {
  page?: number
  per_page?: number
  search?: string
  source_type?: string
  status?: string
}

export async function fetchKnowledge(
  params: FetchKnowledgeParams = {}
): Promise<PaginatedResponse<KnowledgeItem>> {
  const cleanParams: Record<string, string | number> = {}

  if (params.page !== undefined) cleanParams.page = params.page
  if (params.per_page !== undefined) cleanParams.per_page = params.per_page
  if (params.search && params.search.trim()) cleanParams.search = params.search.trim()
  if (params.source_type && params.source_type !== 'all') {
    cleanParams.source_type = params.source_type
  }
  if (params.status && params.status !== 'all') {
    cleanParams.status = params.status
  }

  const response = await client.get<PaginatedResponse<KnowledgeItem>>('/api/knowledge', {
    params: cleanParams,
  })
  return response.data
}

export async function fetchKnowledgeItem(id: string): Promise<KnowledgeItem> {
  const response = await client.get<KnowledgeItem>(`/api/knowledge/${id}`)
  return response.data
}

export async function deleteKnowledgeItem(id: string): Promise<void> {
  await client.delete(`/api/knowledge/${id}`)
}
