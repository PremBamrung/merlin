import Icons from './Icons'

interface SourcePillProps {
  type: string
  label?: string
}

const typeMap: Record<string, { icon: keyof typeof Icons; cls: string; txt: string }> = {
  youtube: { icon: 'yt', cls: 'yt', txt: 'youtube' },
  blog: { icon: 'blog', cls: 'blog', txt: 'blog' },
  article: { icon: 'blog', cls: 'blog', txt: 'article' },
  reddit: { icon: 'reddit', cls: 'reddit', txt: 'reddit' },
  web: { icon: 'web', cls: 'web', txt: 'web' },
  chat: { icon: 'chat', cls: 'chat', txt: 'chat' },
}

export default function SourcePill({ type, label }: SourcePillProps) {
  const m = typeMap[type] || typeMap.web
  const Icon = Icons[m.icon]
  return (
    <span className={`source-pill ${m.cls}`}>
      <Icon /> {label || m.txt}
    </span>
  )
}
