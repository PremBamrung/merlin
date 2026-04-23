import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

const base: IconProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export const Icons = {
  sparkle: (p: IconProps) => <svg {...base} {...p}><path d="M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z"/><path d="M19 3v3M17.5 4.5h3M5 17v3M3.5 18.5h3"/></svg>,
  home: (p: IconProps) => <svg {...base} {...p}><path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-6h-6v6H4a1 1 0 01-1-1z"/></svg>,
  library: (p: IconProps) => <svg {...base} {...p}><path d="M4 5h4v14H4zM10 5h4v14h-4zM17 5l4 1-3 13-4-1z"/></svg>,
  chat: (p: IconProps) => <svg {...base} {...p}><path d="M21 15a2 2 0 01-2 2H8l-5 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>,
  tag: (p: IconProps) => <svg {...base} {...p}><path d="M20 12l-8 8-8-8V4h8z"/><circle cx="8" cy="8" r="1.5"/></svg>,
  graph: (p: IconProps) => <svg {...base} {...p}><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="M8 7.5l8 0M7.5 8l4 8M16.5 8l-4 8"/></svg>,
  inbox: (p: IconProps) => <svg {...base} {...p}><path d="M3 13l3-10h12l3 10M3 13v6a2 2 0 002 2h14a2 2 0 002-2v-6M3 13h5l1.5 2h5L16 13h5"/></svg>,
  search: (p: IconProps) => <svg {...base} {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>,
  plus: (p: IconProps) => <svg {...base} {...p}><path d="M12 5v14M5 12h14"/></svg>,
  settings: (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3h.1a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8v.1a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/></svg>,
  yt: (p: IconProps) => <svg {...base} {...p}><rect x="2" y="5" width="20" height="14" rx="3"/><path d="M10 9l5 3-5 3z" fill="currentColor"/></svg>,
  link: (p: IconProps) => <svg {...base} {...p}><path d="M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1"/></svg>,
  reddit: (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="13" r="8"/><circle cx="9" cy="13" r="1" fill="currentColor"/><circle cx="15" cy="13" r="1" fill="currentColor"/><path d="M9 16c1 1 4.5 1 6 0M16 7a2 2 0 112 2M20 9v0"/></svg>,
  blog: (p: IconProps) => <svg {...base} {...p}><path d="M4 4h12l4 4v12H4z"/><path d="M8 10h8M8 14h8M8 18h5"/></svg>,
  web: (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg>,
  clock: (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  share: (p: IconProps) => <svg {...base} {...p}><path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7M16 6l-4-4-4 4M12 2v13"/></svg>,
  close: (p: IconProps) => <svg {...base} {...p}><path d="M6 6l12 12M18 6L6 18"/></svg>,
  arrowUp: (p: IconProps) => <svg {...base} {...p} strokeWidth={1.8}><path d="M12 19V5M6 11l6-6 6 6"/></svg>,
  paper: (p: IconProps) => <svg {...base} {...p}><path d="M13 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V9zM13 3v6h6M9 13h6M9 17h4"/></svg>,
  filter: (p: IconProps) => <svg {...base} {...p}><path d="M3 5h18l-7 9v6l-4-2v-4z"/></svg>,
  grid: (p: IconProps) => <svg {...base} {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>,
  list: (p: IconProps) => <svg {...base} {...p}><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>,
  check: (p: IconProps) => <svg {...base} {...p} strokeWidth={1.8}><path d="M5 12l5 5L20 7"/></svg>,
  spark: (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>,
  trash: (p: IconProps) => <svg {...base} {...p}><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>,
}

export default Icons
