import { NavLink } from 'react-router-dom'
import Icons from './Icons'
import { TAGS } from '@/data/mockData'

interface SidebarProps {
  active?: string
}

export default function Sidebar({ active }: SidebarProps) {
  const items = [
    { id: 'today', label: 'Today', icon: Icons.sparkle, to: '/today' },
    { id: 'digest', label: 'Digest', icon: Icons.clock, count: 12, to: '/digest' },
    { id: 'inbox', label: 'Inbox', icon: Icons.inbox, count: 3, to: '/inbox' },
    { id: 'library', label: 'Library', icon: Icons.library, count: 248, to: '/library' },
    { id: 'chat', label: 'Chat', icon: Icons.chat, to: '/chat' },
    { id: 'graph', label: 'Graph', icon: Icons.graph, to: '/graph' },
    { id: 'follows', label: 'Voices', icon: Icons.tag, to: '/digest' },
  ]

  const sources = [
    { id: 'youtube', label: 'YouTube', icon: Icons.yt, count: 142, to: '/youtube' },
    { id: 'reddit', label: 'Reddit', icon: Icons.reddit, count: 28, to: '/reddit' },
    { id: 'blogs', label: 'Blogs', icon: Icons.blog, count: 67, to: '/share' },
    { id: 'web', label: 'Web clips', icon: Icons.web, count: 11, to: '/today' },
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
            {it.count != null && <span className="count">{it.count}</span>}
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
            <span className="count">{s.count}</span>
          </NavLink>
        )
      })}

      <div className="side-section">Tags</div>
      {TAGS.slice(0, 5).map((t) => (
        <div key={t.name} className="side-tag">
          <span className="swatch" style={{ background: t.color }} />
          <span>{t.name}</span>
          <span className="count">{t.count}</span>
        </div>
      ))}

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
