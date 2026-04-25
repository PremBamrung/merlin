import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import Icons from './Icons'
import { fetchTags } from '@/api/knowledge'

interface SidebarProps {
  active?: string
}

export default function Sidebar({ active }: SidebarProps) {
  const { data: tags = [] } = useQuery({
    queryKey: ['tags'],
    queryFn: fetchTags,
    staleTime: 60000,
  })

  const items = [
    { id: 'today', label: 'Today', icon: Icons.sparkle, to: '/today' },
    { id: 'digest', label: 'Digest', icon: Icons.clock, to: '/digest' },
    { id: 'inbox', label: 'Inbox', icon: Icons.inbox, to: '/inbox' },
    { id: 'library', label: 'Library', icon: Icons.library, to: '/library' },
    { id: 'chat', label: 'Chat', icon: Icons.chat, to: '/chat' },
    { id: 'graph', label: 'Graph', icon: Icons.graph, to: '/graph' },
  ]

  const sources = [
    { id: 'youtube', label: 'YouTube', icon: Icons.yt, to: '/youtube' },
    { id: 'reddit', label: 'Reddit', icon: Icons.reddit, to: '/reddit' },
    { id: 'blogs', label: 'Blogs', icon: Icons.blog, to: '/share' },
  ]

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
            <Icon /> <span>{it.label}</span>
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
            <div key={t.name} className="side-tag">
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
      </div>
    </aside>
  )
}
