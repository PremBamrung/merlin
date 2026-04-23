import { create } from 'zustand'
import type { ChatMessage, Citation } from '@/types'

interface ChatState {
  messages: ChatMessage[]
  isStreaming: boolean
  addMessage: (msg: ChatMessage) => void
  updateLastMessage: (content: string, citations?: Citation[]) => void
  setStreaming: (v: boolean) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,

  addMessage: (msg) =>
    set((state) => ({
      messages: [...state.messages, msg],
    })),

  updateLastMessage: (content, citations) =>
    set((state) => {
      const messages = [...state.messages]
      const lastIndex = messages.length - 1
      if (lastIndex < 0) return state

      messages[lastIndex] = {
        ...messages[lastIndex],
        content,
        ...(citations !== undefined ? { citations } : {}),
      }
      return { messages }
    }),

  setStreaming: (v) => set({ isStreaming: v }),

  clearMessages: () => set({ messages: [], isStreaming: false }),
}))

export function generateMessageId(): string {
  return crypto.randomUUID()
}
