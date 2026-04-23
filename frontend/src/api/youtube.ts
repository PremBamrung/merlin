import client from './client'

export interface YouTubeSubmitResponse {
  task_id: string
  status: string
}

export async function submitYouTube(
  url: string,
  summary_length: string
): Promise<YouTubeSubmitResponse> {
  const response = await client.post<YouTubeSubmitResponse>('/api/sources/youtube', {
    url,
    summary_length,
  })
  return response.data
}
