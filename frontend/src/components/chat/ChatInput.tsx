import { useRef, useEffect } from 'react'
import { ArrowUp } from 'lucide-react'
import clsx from 'clsx'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
}

export default function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea up to 5 rows
  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 5 + 24 // 5 rows + padding
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
  }, [value])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!disabled && value.trim()) {
        onSend()
      }
    }
  }

  return (
    <div className="border-t border-[#2a2a2a] bg-[#0d0d0d] px-4 py-4">
      <div className={clsx(
        'flex items-end gap-3 bg-[#161616] border rounded-xl px-4 py-3 transition-colors',
        'focus-within:border-[#7c3aed] focus-within:ring-1 focus-within:ring-[#7c3aed]/20',
        disabled ? 'border-[#2a2a2a] opacity-75' : 'border-[#2a2a2a]'
      )}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask Merlin anything..."
          rows={1}
          className={clsx(
            'flex-1 bg-transparent text-[#e8e8e8] text-sm placeholder:text-[#555555]',
            'resize-none outline-none leading-6 py-0',
            'disabled:cursor-not-allowed'
          )}
          style={{ minHeight: '24px' }}
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className={clsx(
            'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150',
            disabled || !value.trim()
              ? 'bg-[#2a2a2a] text-[#555555] cursor-not-allowed'
              : 'bg-[#7c3aed] hover:bg-[#6d28d9] text-white'
          )}
        >
          <ArrowUp size={16} />
        </button>
      </div>
      <p className="text-center text-[10px] text-[#555555] mt-2">
        Shift+Enter for new line · Enter to send
      </p>
    </div>
  )
}
