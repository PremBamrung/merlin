import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Icons from './Icons'
import { fetchTags, fetchKnowledge } from '@/api/knowledge'
import { fetchTasks } from '@/api/tasks'
import { fetchDigest } from '@/api/digest'

interface SidebarProps {
  active?: string
  onSidebarToggle?: () => void
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: 15, height: 15 }}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: 15, height: 15 }}>
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  )
}

export default function Sidebar({ active, onSidebarToggle }: SidebarProps) {
  const navigate = useNavigate()
  const [theme, setTheme] = useState<string>(() => document.documentElement.dataset.theme ?? 'obsidian')

  useEffect(() => {
    const obs = new MutationObserver(() => {
      setTheme(document.documentElement.dataset.theme ?? 'obsidian')
    })
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])

  const { data: tags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: fetchTags,
    staleTime: 60000,
  })

  const { data: libraryData } = useQuery({
    queryKey: ['knowledge', 'sidebar-count'],
    queryFn: () => fetchKnowledge({ per_page: 1, status: 'completed' }),
    staleTime: 30000,
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => fetchTasks(50),
    staleTime: 10000,
  })

  const { data: digestData } = useQuery({
    queryKey: ['digest'],
    queryFn: () => fetchDigest(30),
    staleTime: 60000,
  })

  const libraryCount = libraryData?.total ?? 0
  const inboxCount = tasks.filter((t) => t.status === 'queued' || t.status === 'processing').length
  const digestCount = digestData?.total ?? 0

  const items = [
    { id: 'today', label: 'Today', icon: Icons.sparkle, to: '/today', count: 0 },
    { id: 'digest', label: 'Digest', icon: Icons.clock, to: '/digest', count: digestCount },
    { id: 'inbox', label: 'Inbox', icon: Icons.inbox, to: '/inbox', count: inboxCount },
    { id: 'library', label: 'Library', icon: Icons.library, to: '/library', count: libraryCount },
    { id: 'chat', label: 'Chat', icon: Icons.chat, to: '/chat', count: 0 },
    { id: 'graph', label: 'Graph', icon: Icons.graph, to: '/graph', count: 0 },
  ]

  const sources = [
    { id: 'youtube', label: 'YouTube', icon: Icons.yt, to: '/youtube' },
  ]

  const toggleTheme = () => {
    const next = theme === 'obsidian' ? 'papyrus' : 'obsidian'
    document.documentElement.dataset.theme = next
    localStorage.setItem('merlin-theme', next)
    setTheme(next)
  }

  return (
    <aside className="side">
      <div className="side-brand">
        <div className="mark">✦</div>
        <div className="name">Merlin</div>
      </div>

      <div className="side-section">Workspace</div>
      {items.map((it) => {
        const Icon = it.icon
        const isActive = active === it.id
        return (
          <NavLink
            key={it.id}
            to={it.to}
            className={`side-item${isActive ? ' is-active' : ''}`}
          >
            <Icon />
            <span style={{ flex: 1 }}>{it.label}</span>
            {it.count > 0 && (
              <span style={{
                fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--bg-active)',
                color: 'var(--text-muted)', borderRadius: 10, padding: '1px 6px', marginLeft: 'auto',
              }}>{it.count}</span>
            )}
          </NavLink>
        )
      })}

      <div className="side-section">Sources</div>
      {sources.map((s) => {
        const Icon = s.icon
        const isActive = active === s.id
        return (
          <NavLink
            key={s.id}
            to={s.to}
            className={`side-item${isActive ? ' is-active' : ''}`}
          >
            <Icon /> <span>{s.label}</span>
          </NavLink>
        )
      })}

      {tags.length > 0 && (
        <>
          <div className="side-section">Tags</div>
          {tags.slice(0, 8).map((t) => (
            <div
              key={t.name}
              className="side-tag"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/library?tag=${encodeURIComponent(t.name)}`)}
            >
              <span className="swatch" />
              <span>{t.name}</span>
              <span className="count">{t.count}</span>
            </div>
          ))}
        </>
      )}

      <div className="side-foot">
        <div className="avatar">P</div>
        <div className="who">
          <span>prem</span>
          <small>personal vault</small>
        </div>
        <button
          onClick={toggleTheme}
          title={theme === 'obsidian' ? 'Switch to light theme' : 'Switch to dark theme'}
          style={{
            marginLeft: 'auto', background: 'transparent', border: '1px solid var(--border)',
            borderRadius: 6, padding: '5px 6px', cursor: 'pointer', color: 'var(--text-muted)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all var(--dur)',
          }}
        >
          {theme === 'obsidian' ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </aside>
  )
}
