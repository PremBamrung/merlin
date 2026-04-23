import axios from 'axios'
import type { KnowledgeItem } from '@/types'

const client = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Parse tags and topics fields that may come as JSON strings from the backend.
 */
function parseKnowledgeItem(item: KnowledgeItem): KnowledgeItem {
  // Parse tags: backend may send a JSON string like '["ai","tech"]'
  if (typeof (item.tags as unknown) === 'string') {
    try {
      item.tags = JSON.parse(item.tags as unknown as string)
    } catch {
      item.tags = []
    }
  }
  if (!Array.isArray(item.tags)) {
    item.tags = []
  }

  // Parse topics: backend may send a JSON string
  if (typeof (item.topics as unknown) === 'string') {
    try {
      item.topics = JSON.parse(item.topics as unknown as string)
    } catch {
      item.topics = null
    }
  }

  // Construct thumbnail URL for YouTube if not present
  if (item.source_type === 'youtube' && !item.thumbnail_url && item.source_id) {
    item.thumbnail_url = `https://img.youtube.com/vi/${item.source_id}/hqdefault.jpg`
  }

  return item
}

// Response interceptor to parse knowledge item fields
client.interceptors.response.use((response) => {
  const url = response.config.url || ''
  const data = response.data

  // Single knowledge item
  if (url.match(/\/api\/knowledge\/[^/]+$/) && data && data.id) {
    response.data = parseKnowledgeItem(data)
  }

  // Paginated knowledge list
  if (url.match(/\/api\/knowledge(\?.*)?$/) && data && Array.isArray(data.items)) {
    response.data = {
      ...data,
      items: data.items.map(parseKnowledgeItem),
    }
  }

  return response
})

export { parseKnowledgeItem }
export default client
