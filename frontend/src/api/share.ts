import client from './client'

export interface ShareResponse {
  token: string
  url: string
}

export async function createShare(knowledgeItemId: string): Promise<ShareResponse> {
  const res = await client.post<ShareResponse>('/api/share', { knowledge_item_id: knowledgeItemId })
  return res.data
}
