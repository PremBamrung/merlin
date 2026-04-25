import client from './client'

export interface DigestItem {
  id: string
  source_type: string
  title: string
  author: string | null
  ingested_at: string | null
  summary: string | null
  tags: string[]
  match_score: number
  why: string
}

export interface DigestSection {
  title: string
  subtitle: string
  items: DigestItem[]
}

export interface DigestResponse {
  date: string | null
  total: number
  sections: DigestSection[]
}

export async function fetchDigest(limit = 20): Promise<DigestResponse> {
  const res = await client.get<DigestResponse>('/api/digest/today', { params: { limit } })
  return res.data
}

export async function ingestDigestItem(id: string): Promise<void> {
  await client.post(`/api/digest/${id}/ingest`)
}

export async function skipDigestItem(id: string): Promise<void> {
  await client.post(`/api/digest/${id}/skip`)
}
