import client from './client'

export interface SourceConfig {
  type: string
  display_name: string
  schema: Record<string, unknown>
}

/** Registered knowledge-source plugins the backend can actually ingest. */
export async function fetchConfig(): Promise<SourceConfig[]> {
  const res = await client.get<{ source_types: SourceConfig[] }>('/api/config')
  return res.data.source_types
}
