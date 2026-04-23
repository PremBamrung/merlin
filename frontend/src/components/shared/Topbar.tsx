import type { ReactNode } from 'react'
import Icons from './Icons'

interface TopbarProps {
  crumbs?: string[]
  actions?: ReactNode
}

export default function Topbar({ crumbs = [], actions }: TopbarProps) {
  return (
    <div className="topbar">
      <div className="crumb">
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? 'cur' : ''}>{c}</span>
          </span>
        ))}
      </div>
      <div className="actions">
        {actions || (
          <>
            <button className="btn ghost">
              <Icons.search /> Search <span className="kbd">⌘K</span>
            </button>
            <button className="btn primary">
              <Icons.plus /> Add source
            </button>
          </>
        )}
      </div>
    </div>
  )
}
