import axios from 'axios'
import type { KnowledgeItem } from '@/types'

const client = axios.create({
  baseURL: '',
  headers: { 'Content-Type': 'application/json' },
})

function parseKnowledgeItem(item: KnowledgeItem): KnowledgeItem {
  if (typeof (item.tags as unknown) === 'string') {
    try { item.tags = JSON.parse(item.tags as unknown as string) }
    catch { item.tags = [] }
  }
  if (!Array.isArray(item.tags)) item.tags = []

  if (typeof (item.topics as unknown) === 'string') {
    try { item.topics = JSON.parse(item.topics as unknown as string) }
    catch { item.topics = null }
  }

  if (item.source_type === 'youtube' && !item.thumbnail_url && item.source_id) {
    item.thumbnail_url = `https://img.youtube.com/vi/${item.source_id}/hqdefault.jpg`
  }

  return item
}

client.interceptors.response.use((response) => {
  const url = response.config.url || ''
  const data = response.data

  if (url.match(/\/api\/knowledge\/[^/]+$/) && data?.id) {
    response.data = parseKnowledgeItem(data)
  }
  if (url.match(/\/api\/knowledge(\?.*)?$/) && data && Array.isArray(data.items)) {
    response.data = { ...data, items: data.items.map(parseKnowledgeItem) }
  }

  return response
})

export { parseKnowledgeItem }
export default client
