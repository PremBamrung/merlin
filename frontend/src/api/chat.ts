import type { Citation } from '@/types'

export interface ChatRequestMessage {
  role: string
  content: string
}

export function streamChat(
  messages: ChatRequestMessage[],
  onChunk: (content: string) => void,
  onCitations: (citations: Citation[]) => void,
  onDone: () => void,
  onError: (msg: string) => void
): AbortController {
  const controller = new AbortController()

  async function run() {
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({ messages }),
        signal: controller.signal,
      })

      if (!response.ok) {
        onError(`HTTP ${response.status}: ${await response.text()}`)
        return
      }
      if (!response.body) { onError('No response body'); return }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice('data: '.length).trim()
          if (!jsonStr || jsonStr === '[DONE]') continue

          try {
            const event = JSON.parse(jsonStr) as {
              type: string; content?: string; sources?: Citation[]; message?: string
            }
            switch (event.type) {
              case 'chunk': if (event.content !== undefined) onChunk(event.content); break
              case 'citations': if (event.sources) onCitations(event.sources); break
              case 'done': onDone(); return
              case 'error': onError(event.message || 'Unknown streaming error'); return
            }
          } catch { /* non-JSON lines */ }
        }
      }
      onDone()
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      onError(err instanceof Error ? err.message : 'Stream error')
    }
  }

  run()
  return controller
}
