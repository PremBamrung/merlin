import client from './client'

export interface YouTubeSubmitResponse {
  task_id: string
  status: string
}

export async function submitYouTube(
  urlOrParams: string | { url: string; summary_length?: string },
  summary_length = 'medium'
): Promise<YouTubeSubmitResponse> {
  const body = typeof urlOrParams === 'string'
    ? { url: urlOrParams, summary_length }
    : { summary_length: 'medium', ...urlOrParams }
  const res = await client.post<YouTubeSubmitResponse>('/api/sources/youtube', body)
  return res.data
}

export async function retryYouTube(itemId: string): Promise<YouTubeSubmitResponse> {
  const res = await client.post<YouTubeSubmitResponse>(`/api/sources/youtube/${itemId}/retry`)
  return res.data
}
