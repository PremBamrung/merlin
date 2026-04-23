import { useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { useChatStore, generateMessageId } from '@/stores/chatStore'
import { streamChat } from '@/api/chat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'

export default function ChatWindow() {
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const addMessage = useChatStore((s) => s.addMessage)
  const updateLastMessage = useChatStore((s) => s.updateLastMessage)
  const setStreaming = useChatStore((s) => s.setStreaming)

  // Scroll to bottom on new messages or content updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSend() {
    const content = inputValue.trim()
    if (!content || isStreaming) return

    // Cancel any existing stream
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }

    // Add user message
    addMessage({
      id: generateMessageId(),
      role: 'user',
      content,
    })

    // Add empty assistant message placeholder
    addMessage({
      id: generateMessageId(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    })

    setStreaming(true)
    setInputValue('')

    // Build message history for API (all messages including the new user one)
    const currentMessages = useChatStore.getState().messages
    const apiMessages = currentMessages
      .filter((m) => !m.isStreaming)
      .map((m) => ({ role: m.role, content: m.content }))

    let accumulatedContent = ''

    const controller = streamChat(
      apiMessages,
      // onChunk
      (chunk) => {
        accumulatedContent += chunk
        updateLastMessage(accumulatedContent)
      },
      // onCitations
      (citations) => {
        updateLastMessage(accumulatedContent, citations)
      },
      // onDone
      () => {
        // Mark last message as not streaming
        const store = useChatStore.getState()
        const msgs = store.messages
        const lastIdx = msgs.length - 1
        if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
          const updated = { ...msgs[lastIdx], isStreaming: false }
          useChatStore.setState({
            messages: [...msgs.slice(0, lastIdx), updated],
            isStreaming: false,
          })
        } else {
          setStreaming(false)
        }
        abortRef.current = null
      },
      // onError
      (errMsg) => {
        const store = useChatStore.getState()
        const msgs = store.messages
        const lastIdx = msgs.length - 1
        if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
          const updated = {
            ...msgs[lastIdx],
            content: accumulatedContent || `Error: ${errMsg}`,
            isStreaming: false,
          }
          useChatStore.setState({
            messages: [...msgs.slice(0, lastIdx), updated],
            isStreaming: false,
          })
        } else {
          setStreaming(false)
        }
        abortRef.current = null
      }
    )

    abortRef.current = controller
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4">
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 px-8 text-center">
            <div className="w-14 h-14 bg-[#7c3aed]/20 border border-[#7c3aed]/30 rounded-2xl flex items-center justify-center">
              <Sparkles size={28} className="text-[#a78bfa]" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-[#e8e8e8] mb-1">Ask Merlin</h2>
              <p className="text-sm text-[#555555] max-w-sm">
                Ask anything about your knowledge base. Merlin will search across your saved YouTube videos, articles, and documents.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 w-full max-w-sm mt-2">
              {[
                'Summarize what I know about machine learning',
                'What videos have I saved about TypeScript?',
                'Key takeaways from my recent additions',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => { setInputValue(suggestion) }}
                  className="text-left px-3 py-2.5 bg-[#161616] border border-[#2a2a2a] hover:border-[#3d3d3d] rounded-lg text-sm text-[#888888] hover:text-[#e8e8e8] transition-all duration-150"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-2 pb-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSend}
        disabled={isStreaming}
      />
    </div>
  )
}
