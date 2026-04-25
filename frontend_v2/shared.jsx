/* global React */
const { useState, useEffect, useMemo, useRef } = React;

// ============================================================
// Icons — single-source-of-truth inline SVG, minimal strokes
// ============================================================
const I = {
  sparkle: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z"/><path d="M19 3v3M17.5 4.5h3M5 17v3M3.5 18.5h3"/></svg>,
  home: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-6h-6v6H4a1 1 0 01-1-1z"/></svg>,
  library: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 5h4v14H4zM10 5h4v14h-4zM17 5l4 1-3 13-4-1z"/></svg>,
  chat: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 15a2 2 0 01-2 2H8l-5 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>,
  tag: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M20 12l-8 8-8-8V4h8z"/><circle cx="8" cy="8" r="1.5"/></svg>,
  graph: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7.5l8 0M7.5 8l4 8M16.5 8l-4 8"/></svg>,
  inbox: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 13l3-10h12l3 10M3 13v6a2 2 0 002 2h14a2 2 0 002-2v-6M3 13h5l1.5 2h5L16 13h5"/></svg>,
  search: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>,
  plus: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 5v14M5 12h14"/></svg>,
  settings: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3h.1a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8v.1a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/></svg>,
  yt: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M10 9l5 3-5 3z" fill="currentColor"/></svg>,
  link: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1"/></svg>,
  reddit: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="13" r="8"/><circle cx="9" cy="13" r="1" fill="currentColor"/><circle cx="15" cy="13" r="1" fill="currentColor"/><path d="M9 16c1 1 4.5 1 6 0M16 7a2 2 0 112 2M20 9v0"/></svg>,
  blog: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 4h12l4 4v12H4z"/><path d="M8 10h8M8 14h8M8 18h5"/></svg>,
  web: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg>,
  clock: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  share: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7M16 6l-4-4-4 4M12 2v13"/></svg>,
  close: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 6l12 12M18 6L6 18"/></svg>,
  arrowUp: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 19V5M6 11l6-6 6 6"/></svg>,
  paper: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M13 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V9zM13 3v6h6M9 13h6M9 17h4"/></svg>,
  filter: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 5h18l-7 9v6l-4-2v-4z"/></svg>,
  grid: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>,
  list: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>,
  check: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M5 12l5 5L20 7"/></svg>,
  spark: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>,
};

// ============================================================
// Sidebar — shared between screens
// ============================================================
function Sidebar({ active, tagFilter, onNav }) {
  const items = [
    { id: 'today', label: 'Today', icon: I.sparkle },
    { id: 'digest', label: 'Digest', icon: I.clock, count: 12 },
    { id: 'inbox', label: 'Inbox', icon: I.inbox, count: 3 },
    { id: 'library', label: 'Library', icon: I.library, count: 248 },
    { id: 'chat', label: 'Chat', icon: I.chat },
    { id: 'graph', label: 'Graph', icon: I.graph },
    { id: 'follows', label: 'Voices', icon: I.tag },
  ];
  const sources = [
    { id: 'youtube', label: 'YouTube', icon: I.yt, count: 142 },
    { id: 'blogs', label: 'Blogs', icon: I.blog, count: 67 },
    { id: 'reddit', label: 'Reddit', icon: I.reddit, count: 28 },
    { id: 'web', label: 'Web clips', icon: I.web, count: 11 },
  ];
  const tags = [
    { name: 'llm-research', color: '#c9a9ff', count: 34 },
    { name: 'rust', color: '#e8a87c', count: 22 },
    { name: 'design-systems', color: '#8db089', count: 18 },
    { name: 'woodworking', color: '#d99547', count: 14 },
    { name: 'longevity', color: '#7ba2c9', count: 9 },
  ];
  return (
    <aside className="side">
      <div className="side-brand">
        <div className="mark">✦</div>
        <div className="name">Merlin</div>
      </div>

      <div className="side-section">Workspace</div>
      {items.map(it => {
        const Icon = it.icon;
        return (
          <div key={it.id} className={"side-item" + (active === it.id ? ' is-active' : '')} onClick={() => onNav && onNav(it.id)}>
            <Icon /> <span>{it.label}</span>
            {it.count != null && <span className="count">{it.count}</span>}
          </div>
        );
      })}

      <div className="side-section">Sources</div>
      {sources.map(s => {
        const Icon = s.icon;
        return (
          <div key={s.id} className={"side-item" + (active === s.id ? ' is-active' : '')} onClick={() => onNav && onNav(s.id)}>
            <Icon /> <span>{s.label}</span>
            <span className="count">{s.count}</span>
          </div>
        );
      })}

      <div className="side-section">Tags</div>
      {tags.map(t => (
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
  );
}

// ============================================================
// Topbar
// ============================================================
function Topbar({ crumbs = [], actions }) {
  return (
    <div className="topbar">
      <div className="crumb">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? 'cur' : ''}>{c}</span>
          </React.Fragment>
        ))}
      </div>
      <div className="actions">
        {actions || (
          <>
            <div className="btn ghost"><I.search /> Search <span className="kbd">⌘K</span></div>
            <div className="btn primary"><I.plus /> Add source</div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================
// Source pill — yt/blog/reddit/web
// ============================================================
function SourcePill({ type, label }) {
  const map = {
    youtube: { Icon: I.yt, cls: 'yt', txt: 'youtube' },
    blog: { Icon: I.blog, cls: 'blog', txt: 'blog' },
    reddit: { Icon: I.reddit, cls: 'reddit', txt: 'reddit' },
    web: { Icon: I.web, cls: 'web', txt: 'web' },
    chat: { Icon: I.chat, cls: 'chat', txt: 'chat' },
  };
  const m = map[type] || map.web;
  const Icon = m.Icon;
  return (
    <span className={"source-pill " + m.cls}>
      <Icon /> {label || m.txt}
    </span>
  );
}

// Expose for other script files
Object.assign(window, { I, Sidebar, Topbar, SourcePill });
