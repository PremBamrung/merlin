export interface KnowledgeItem {
  id: string;
  source_type: 'youtube' | 'article' | 'pdf';
  source_id: string;
  title: string;
  author: string | null;
  published_at: string | null;
  ingested_at: string;
  summary: string | null;
  summary_length: string | null;
  tags: string[];
  topics: Record<string, string> | null;
  llm_model: string | null;
  word_count: number | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message: string | null;
  thumbnail_url?: string | null;
  views?: number | null;
  duration?: string | null;
  channel?: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

export interface Citation {
  id: string;
  title: string;
  source_type: string;
  author: string | null;
}

export interface Task {
  task_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string | null;
  result?: { knowledge_item_id?: string };
  error?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
