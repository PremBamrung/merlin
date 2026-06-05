import client from './client'

export interface YouTubeSubmitResponse {
  task_id: string
  status: string
}

export async function submitYouTube(
  urlOrParams: string | { url: string; summary_length?: string; languages?: string[] },
  summary_length = 'short'
): Promise<YouTubeSubmitResponse> {
  const body = typeof urlOrParams === 'string'
    ? { url: urlOrParams, summary_length }
    : { summary_length: 'short', languages: ['en', 'fr'], ...urlOrParams }
  const res = await client.post<YouTubeSubmitResponse>('/api/sources/youtube', body)
  return res.data
}

export async function retryYouTube(itemId: string): Promise<YouTubeSubmitResponse> {
  const res = await client.post<YouTubeSubmitResponse>(`/api/sources/youtube/${itemId}/retry`)
  return res.data
}

export async function clearYouTubeSummary(itemId: string): Promise<{ ok: boolean }> {
  const res = await client.delete<{ ok: boolean }>(`/api/sources/youtube/${itemId}/summary`)
  return res.data
}

/**
 * Regenerate a YouTube item's summary: clear it (resets status → pending,
 * keeps the transcript) then re-enqueue ingestion via retry.
 */
export async function regenerateYouTubeSummary(itemId: string): Promise<YouTubeSubmitResponse> {
  await clearYouTubeSummary(itemId)
  return retryYouTube(itemId)
}
