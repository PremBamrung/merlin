import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import { useChatStore, generateMessageId } from '@/stores/chatStore'
import { streamChat } from '@/api/chat'
import { fetchTags } from '@/api/knowledge'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const SUGGESTIONS = [
  "What did Karpathy say about RLHF vs SFT?",
  "Summarize my llm-research sources into 5 bullets",
  "Which authors disagreed with each other?",
  "What topics am I exploring most lately?",
]

const ALL_SOURCE_TYPES = ['youtube', 'article', 'pdf'] as const

export default function ChatPage() {
  const location = useLocation()
  const { messages, isStreaming, addMessage, updateLastMessage, setStreaming, clearMessages } = useChatStore()

  const initialQuery = (location.state as { initialQuery?: string } | null)?.initialQuery ?? ''
  const [input, setInput] = useState(initialQuery)
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { data: tags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: fetchTags,
    staleTime: 60000,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (initialQuery) {
      textareaRef.current?.focus()
    }
  }, [initialQuery])

  const toggleSource = (type: string) => {
    setSelectedSources((prev) =>
      prev.includes(type) ? prev.filter((s) => s !== type) : [...prev, type]
    )
  }

  const toggleTag = (name: string) => {
    setSelectedTags((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    )
  }

  const contextFilters = {
    source_types: selectedSources.length > 0 ? selectedSources : undefined,
    tags: selectedTags.length > 0 ? selectedTags : undefined,
  }

  const activeFilterCount = selectedSources.length + selectedTags.length

  const footerLabel = activeFilterCount > 0
    ? `${activeFilterCount} filter${activeFilterCount !== 1 ? 's' : ''} active`
    : 'full vault · all sources'

  const send = () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')

    addMessage({ id: generateMessageId(), role: 'user', content: text })
    const assistantId = generateMessageId()
    addMessage({ id: assistantId, role: 'assistant', content: '', isStreaming: true })
    setStreaming(true)

    const history = messages.map((m) => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content }))
    history.push({ role: 'user', content: text })

    abortRef.current = streamChat(
      history,
      (chunk) => {
        useChatStore.getState().updateLastMessage(
          (useChatStore.getState().messages.at(-1)?.content ?? '') + chunk
        )
      },
      (citations) => { updateLastMessage(useChatStore.getState().messages.at(-1)?.content ?? '', citations) },
      () => { setStreaming(false) },
      (err) => {
        updateLastMessage(`Error: ${err}`)
        setStreaming(false)
      },
      contextFilters
    )
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const abort = () => { abortRef.current?.abort(); setStreaming(false) }

  return (
    <div className="artboard-root">
      <Sidebar active="chat" />
      <div className="main">
        <Topbar
          crumbs={['Chat']}
          actions={
            <>
              {messages.length > 0 && (
                <button className="btn ghost" onClick={clearMessages}>
                  <Icons.close /> Clear
                </button>
              )}
              <button className="btn primary" onClick={() => { clearMessages(); setInput('') }}>
                <Icons.plus /> New chat
              </button>
            </>
          }
        />

        <div className="chat-layout">
          {/* Context rail */}
          <div className="chat-ctx">
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 14 }}>Context</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-subtle)', marginBottom: 12 }}>Filter what Merlin searches.</div>

            <div className="ctx-section-label">Sources</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }}>
              {ALL_SOURCE_TYPES.map((type) => (
                <label key={type} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 6px', borderRadius: 6, transition: 'background var(--dur)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(type)}
                    onChange={() => toggleSource(type)}
                    style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: 12.5, color: 'var(--text-muted)', textTransform: 'capitalize' }}>{type}</span>
                </label>
              ))}
            </div>

            {tags.length > 0 && (
              <>
                <div className="ctx-section-label">Tags</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
                  {tags.map((t) => (
                    <label key={t.name} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 6px', borderRadius: 6, transition: 'background var(--dur)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTags.includes(t.name)}
                        onChange={() => toggleTag(t.name)}
                        style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
                      />
                      <span style={{ fontSize: 12.5, color: 'var(--text-muted)', flex: 1 }}>{t.name}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-faint)' }}>{t.count}</span>
                    </label>
                  ))}
                </div>
              </>
            )}

            {activeFilterCount > 0 && (
              <button
                onClick={() => { setSelectedSources([]); setSelectedTags([]) }}
                style={{ marginTop: 12, background: 'transparent', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px', fontSize: 11, color: 'var(--text-subtle)', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                Clear filters
              </button>
            )}
          </div>

          {/* Chat main */}
          <div className="chat-main">
            <div className="chat-messages">
              {messages.length === 0 && (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', paddingBottom: 60 }}>
                  <div style={{ fontSize: 40, marginBottom: 12, color: 'var(--accent)' }}>✦</div>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 28, margin: '0 0 8px', fontWeight: 700 }}>Ask your library</h2>
                  <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '0 0 32px', textAlign: 'center' }}>
                    Merlin searches across everything you've saved
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, maxWidth: 560 }}>
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => { setInput(s); textareaRef.current?.focus() }}
                        style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 14px', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, cursor: 'pointer', color: 'var(--text-muted)', background: 'transparent', fontFamily: 'inherit', textAlign: 'left', transition: 'all var(--dur)' }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border-accent)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text)'; (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-1)' }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)'; (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                      >
                        <Icons.chat style={{ width: 14, height: 14, color: 'var(--accent)', flexShrink: 0, marginTop: 1 }} />
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div key={msg.id} className={`chat-msg chat-msg-${msg.role === 'user' ? 'user' : 'merlin'}`}>
                  {msg.role === 'assistant' && <div className="chat-mark">✦</div>}
                  <div>
                    {msg.role === 'assistant' && <div className="merlin-label">Merlin {msg.isStreaming && <span style={{ color: 'var(--accent)' }}>…</span>}</div>}
                    {msg.role === 'user' && <div className="user-label">you</div>}
                    <div className="chat-bubble">
                      {msg.role === 'assistant' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content || (msg.isStreaming ? '…' : '')}</ReactMarkdown>
                      ) : (
                        <span>{msg.content}</span>
                      )}
                      {msg.citations && msg.citations.length > 0 && (
                        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                          {msg.citations.map((c) => (
                            <span key={c.id} className="cite">
                              {c.source_type === 'youtube' ? <Icons.yt style={{ width: 10, height: 10 }} /> : <Icons.paper style={{ width: 10, height: 10 }} />}
                              {c.title}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="chat-input-wrap">
              <div className="chat-input-box">
                <textarea
                  ref={textareaRef}
                  rows={2}
                  placeholder="Ask about your library… (Shift+Enter for new line)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKey}
                />
                <div className="chat-input-footer">
                  <span className="mono" style={{ fontSize: 10.5, color: activeFilterCount > 0 ? 'var(--accent)' : 'var(--text-subtle)' }}>
                    {footerLabel}
                  </span>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                    {isStreaming ? (
                      <button className="btn ghost" onClick={abort} style={{ fontSize: 11.5 }}>Stop</button>
                    ) : (
                      <button
                        className="btn primary"
                        onClick={send}
                        disabled={!input.trim()}
                        style={{ padding: '4px 12px' }}
                      >
                        <Icons.arrowUp style={{ width: 12, height: 12 }} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
