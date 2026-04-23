import { NavLink } from 'react-router-dom'
import { MessageSquare, BookOpen, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import clsx from 'clsx'
import { useUIStore } from '@/stores/uiStore'

interface NavItemProps {
  to: string
  icon: React.ReactNode
  label: string
}

function NavItem({ to, icon, label }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        clsx(
          'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 relative',
          isActive
            ? 'bg-[#7c3aed]/20 text-[#a78bfa] border-l-2 border-[#7c3aed] pl-[10px]'
            : 'text-[#888888] hover:text-[#e8e8e8] hover:bg-[#1f1f1f]'
        )
      }
    >
      <span className="w-4 h-4 flex-shrink-0">{icon}</span>
      <span>{label}</span>
    </NavLink>
  )
}

function ConnectionStatus() {
  const [connected, setConnected] = useState<boolean | null>(null)

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('/api/health')
        const data = await res.json()
        setConnected(res.ok && data?.status === 'ok')
      } catch {
        setConnected(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30_000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span
        className={clsx(
          'w-2 h-2 rounded-full flex-shrink-0 transition-colors',
          connected === null
            ? 'bg-[#555555]'
            : connected
              ? 'bg-[#10b981]'
              : 'bg-[#555555]'
        )}
      />
      <span className="text-xs text-[#555555]">
        {connected === null ? 'Checking...' : connected ? 'Connected' : 'Offline'}
      </span>
    </div>
  )
}

export default function Sidebar() {
  const setAddSourceOpen = useUIStore((s) => s.setAddSourceOpen)

  return (
    <aside className="w-[240px] min-w-[240px] h-full bg-[#0d0d0d] border-r border-[#2a2a2a] flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-[#2a2a2a]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-[#7c3aed] rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm leading-none">M</span>
          </div>
          <span className="text-[#e8e8e8] font-semibold text-lg tracking-tight">Merlin</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <NavItem
          to="/chat"
          icon={<MessageSquare size={16} />}
          label="Chat"
        />
        <NavItem
          to="/knowledge"
          icon={<BookOpen size={16} />}
          label="Knowledge"
        />
      </nav>

      {/* Bottom section */}
      <div className="px-3 py-4 border-t border-[#2a2a2a] space-y-2">
        <button
          onClick={() => setAddSourceOpen(true)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-sm font-medium rounded-lg transition-colors duration-150"
        >
          <Plus size={16} />
          <span>Add Source</span>
        </button>

        <ConnectionStatus />
      </div>
    </aside>
  )
}
