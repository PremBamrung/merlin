import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Youtube, FileText, BookOpen } from 'lucide-react'
import type { ChatMessage } from '@/types'

interface MessageBubbleProps {
  message: ChatMessage
}

const sourceIcons: Record<string, React.ReactNode> = {
  youtube: <Youtube size={10} />,
  article: <FileText size={10} />,
  pdf: <BookOpen size={10} />,
}

function CitationChips({ message }: { message: ChatMessage }) {
  const citations = message.citations
  if (!citations || citations.length === 0) return null

  const visible = citations.slice(0, 3)
  const overflow = citations.length - 3

  return (
    <div className="flex flex-wrap gap-1.5 mt-2.5 pt-2.5 border-t border-[#2a2a2a]">
      <span className="text-[10px] text-[#555555] w-full mb-0.5">Sources:</span>
      {visible.map((c) => (
        <span
          key={c.id}
          className="inline-flex items-center gap-1 px-2 py-0.5 bg-[#1f1f1f] border border-[#2a2a2a] rounded-full text-[10px] text-[#888888] max-w-[160px]"
          title={c.title}
        >
          <span className="text-[#555555] flex-shrink-0">
            {sourceIcons[c.source_type] ?? <FileText size={10} />}
          </span>
          <span className="truncate">{c.title}</span>
        </span>
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center px-2 py-0.5 bg-[#1f1f1f] border border-[#2a2a2a] rounded-full text-[10px] text-[#555555]">
          +{overflow} more
        </span>
      )}
    </div>
  )
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end px-4 py-1">
        <div className="max-w-[80%] px-4 py-2.5 bg-[#7c3aed] text-white text-sm rounded-xl rounded-br-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div className="flex justify-start px-4 py-1">
      <div className="max-w-[85%] min-w-0">
        <div className="bg-[#161616] border border-[#2a2a2a] rounded-xl rounded-bl-sm px-4 py-3">
          {message.content || message.isStreaming ? (
            <div className="prose text-sm">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && (
                <span
                  className="inline-block w-0.5 h-4 bg-[#7c3aed] animate-blink ml-0.5 align-middle"
                  aria-hidden="true"
                />
              )}
            </div>
          ) : (
            // Empty state while starting to stream
            <span
              className="inline-block w-0.5 h-4 bg-[#7c3aed] animate-blink align-middle"
              aria-hidden="true"
            />
          )}

          <CitationChips message={message} />
        </div>
      </div>
    </div>
  )
}
