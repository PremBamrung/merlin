import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { fetchTasks } from '@/api/tasks'
import { fetchKnowledge } from '@/api/knowledge'
import { fetchDigest } from '@/api/digest'
import { submitYouTube } from '@/api/youtube'
import { fetchConfig } from '@/api/config'
import type { Task } from '@/types'

const IS_URL = /https?:\/\/|youtu|\.com\/|\.org\//

function taskStage(t: Task): string {
  if (t.status === 'queued') return 'queued'
  if (t.status === 'processing') return 'processing'
  if (t.status === 'completed') return 'done'
  if (t.status === 'failed') return 'failed'
  return t.status
}

export default function TodayPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [input, setInput] = useState('')
  const [focused, setFocused] = useState(false)

  const { data: tasksData } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => fetchTasks(20),
    refetchInterval: 3000,
  })

  const { data: recentData } = useQuery({
    queryKey: ['knowledge', { per_page: 4 }],
    queryFn: () => fetchKnowledge({ per_page: 4 }),
  })

  const { data: digestData } = useQuery({
    queryKey: ['digest'],
    queryFn: () => fetchDigest(10),
    staleTime: 60000,
  })

  const { data: statsData } = useQuery({
    queryKey: ['knowledge', 'stats'],
    queryFn: () => fetchKnowledge({ per_page: 1, status: 'completed' }),
    staleTime: 30000,
  })

  const { data: sourceTypes = [] } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
    staleTime: Infinity,
  })

  const ingestMutation = useMutation({
    mutationFn: (url: string) => submitYouTube({ url, summary_length: 'short' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  // When an ingestion task finishes, the polled tasks query sees it before the
  // "Recently added" list does (knowledge query has a 30s staleTime). Detect the
  // transition to "completed" and invalidate knowledge queries so the list and
  // stats refetch right away instead of after the stale window.
  const completedTaskIds = useRef<Set<string>>(new Set())
  useEffect(() => {
    const tasks = tasksData ?? []
    let hasNewlyCompleted = false
    for (const t of tasks) {
      if (t.status === 'completed' && !completedTaskIds.current.has(t.task_id)) {
        completedTaskIds.current.add(t.task_id)
        hasNewlyCompleted = true
      }
    }
    if (hasNewlyCompleted) {
      qc.invalidateQueries({ queryKey: ['knowledge'] })
    }
  }, [tasksData, qc])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        document.getElementById('omnibox-input')?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const activeTasks = (tasksData ?? []).filter((t) => t.status !== 'completed')

  const hint = input.trim() === ''
    ? 'Paste a link, drop a YouTube URL, or ask Merlin about your library…'
    : IS_URL.test(input)
      ? 'Press ↵ to ingest this source'
      : 'Press ↵ to ask your library'

  const handleSubmit = () => {
    const val = input.trim()
    if (!val) return
    setInput('')
    if (IS_URL.test(val)) {
      ingestMutation.mutate(val)
    } else {
      navigate('/chat', { state: { initialQuery: val } })
    }
  }

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' || !input.trim()) return
    handleSubmit()
  }

  const recentItems = recentData?.items ?? []
  const digestItems = (digestData?.sections ?? []).flatMap((s) => s.items).slice(0, 3)
  const totalItems = statsData?.total ?? recentData?.total ?? 0

  const thisWeek = recentItems.filter((item) => {
    const d = new Date(item.ingested_at)
    return Date.now() - d.getTime() < 7 * 24 * 60 * 60 * 1000
  }).length

  return (
    <div className="artboard-root">
      <Sidebar active="today" />
      <div className="main">
        <Topbar crumbs={['Home', 'Today']} />
        <div className="page">
          <div className="today-outer">
            {/* Header */}
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
                <span className="mono" style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                </span>
                <span className="text-subtle">·</span>
                <span className="text-subtle mono" style={{ fontSize: 11 }}>{totalItems} sources in library</span>
              </div>
              <h1 className="page-title">Good morning. <span className="dim">What are we learning?</span></h1>
            </div>

            <div className="today-layout">
              {/* Left: omnibox + queue + recent */}
              <div className="today-left">
                {/* Omnibox */}
                <div className={`omnibox${focused ? ' is-focused' : ''}`}>
                  <div className="omnibox-input">
                    <Icons.sparkle style={{ width: 18, height: 18, color: 'var(--accent)', flexShrink: 0 }} />
                    <input
                      className="omnibox-field"
                      placeholder="Paste a link, drop a YouTube URL, or ask Merlin…"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onFocus={() => setFocused(true)}
                      onBlur={() => setFocused(false)}
                      onKeyDown={handleKey}
                      id="omnibox-input"
                    />
                    <button
                      className="btn primary"
                      disabled={!input.trim() || ingestMutation.isPending}
                      onClick={handleSubmit}
                    >
                      <Icons.arrowUp /> Send
                    </button>
                  </div>
                  <div className="omnibox-hint">
                    <span>{hint}</span>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>accepts</span>
                      {sourceTypes.map((s) => (
                        <SourcePill key={s.type} type={s.type === 'article' ? 'blog' : s.type} />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Queue */}
                {activeTasks.length > 0 && (
                  <div style={{ marginTop: 28 }}>
                    <div className="section-head">
                      <span className="section-title">Ingesting</span>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{activeTasks.length} in queue</span>
                      <span className="text-subtle" style={{ fontSize: 12, cursor: 'pointer', marginLeft: 8 }} onClick={() => navigate('/inbox')}>
                        View all →
                      </span>
                    </div>
                    <div style={{ display: 'grid', gap: 8 }}>
                      {activeTasks.slice(0, 3).map((t) => {
                        const stage = taskStage(t)
                        return (
                          <div key={t.task_id} className="queue-row">
                            <div className="queue-dot" data-stage={stage} />
                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontSize: 13.5, fontWeight: 500 }}>{t.message ?? t.task_type}</span>
                              </div>
                              <div className="queue-bar"><div style={{ width: `${t.progress}%` }} /></div>
                            </div>
                            <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                              {stage}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Recent */}
                <div style={{ marginTop: 36 }}>
                  <div className="section-head">
                    <span className="section-title">Recently added</span>
                    <span className="text-subtle" style={{ fontSize: 12, cursor: 'pointer' }} onClick={() => navigate('/library')}>
                      View library →
                    </span>
                  </div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {recentItems.map((s) => (
                      <div key={s.id} className="recent-row" onClick={() => navigate(`/library/${s.id}`)}>
                        <div className="recent-thumb">
                          {s.thumbnail_url ? (
                            <img src={s.thumbnail_url} alt={s.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          ) : (
                            <>
                              {s.source_type === 'youtube' && <Icons.yt style={{ width: 20, height: 20 }} />}
                              {s.source_type === 'article' && <Icons.paper style={{ width: 20, height: 20 }} />}
                              {s.source_type === 'pdf' && <Icons.paper style={{ width: 20, height: 20 }} />}
                            </>
                          )}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
                            <SourcePill type={s.source_type === 'article' ? 'blog' : s.source_type} />
                            {s.channel && <span className="text-subtle" style={{ fontSize: 11 }}>{s.channel}</span>}
                            {s.author && !s.channel && <span className="text-subtle" style={{ fontSize: 11 }}>{s.author}</span>}
                            <span className="text-subtle">·</span>
                            <span className="text-subtle mono" style={{ fontSize: 10.5 }}>
                              {s.ingested_at ? new Date(s.ingested_at).toLocaleDateString() : ''}
                            </span>
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{s.title}</div>
                          {s.summary && (
                            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.45, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' } as React.CSSProperties}>
                              {s.summary}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {recentItems.length === 0 && (
                      <div style={{ color: 'var(--text-subtle)', fontSize: 13.5, padding: '12px 0' }}>
                        No sources yet — paste a YouTube URL above to get started.
                      </div>
                    )}
                  </div>
                </div>

                {/* Ask your library */}
                <div style={{ marginTop: 40 }}>
                  <div className="section-head">
                    <span className="section-title">Ask your library</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {[
                      'What did Karpathy say about RLHF vs SFT?',
                      'Summarize my llm-research tag into 5 bullets',
                      'Which blogs disagreed with each other?',
                      'What am I avoiding learning lately?',
                    ].map((q, i) => (
                      <div key={i} className="prompt-chip" onClick={() => navigate('/chat', { state: { initialQuery: q } })}>
                        <Icons.chat style={{ width: 14, height: 14, color: 'var(--accent)', flexShrink: 0 }} />
                        <span>{q}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: mini-digest + stats */}
              <div className="today-right">
                {/* Quick stats */}
                <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px', marginBottom: 20 }}>
                  <div className="section-title" style={{ marginBottom: 12 }}>Library stats</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {[
                      { label: 'total sources', value: String(totalItems) },
                      { label: 'added this week', value: String(thisWeek) },
                    ].map(({ label, value }) => (
                      <div key={label}>
                        <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-ui)', lineHeight: 1 }}>{value}</div>
                        <div style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Mini-digest */}
                {digestItems.length > 0 && (
                  <div>
                    <div className="section-head">
                      <span className="section-title">From your digest</span>
                      <span className="text-subtle" style={{ fontSize: 12, cursor: 'pointer' }} onClick={() => navigate('/digest')}>
                        Full digest →
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {digestItems.map((item) => (
                        <div
                          key={item.id}
                          onClick={() => navigate(`/library/${item.id}`)}
                          style={{ padding: '10px 12px', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer', transition: 'border-color var(--dur)' }}
                          onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-accent)')}
                          onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                            <SourcePill type={item.source_type === 'article' ? 'blog' : item.source_type} />
                            {item.author && <span className="text-subtle" style={{ fontSize: 11 }}>{item.author}</span>}
                          </div>
                          <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' } as React.CSSProperties}>
                            {item.title}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .today-outer { max-width: 1400px; margin: 0 auto; }
        .today-layout { display: grid; grid-template-columns: 1fr; gap: 32px; }
        @media (min-width: 1200px) {
          .today-layout { grid-template-columns: 3fr 2fr; }
        }
        .today-left {}
        .today-right {}
        .omnibox {
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 14px;
          padding: 4px;
          transition: border-color var(--dur), box-shadow var(--dur);
        }
        .omnibox.is-focused {
          border-color: var(--border-accent);
          box-shadow: 0 0 0 4px var(--accent-soft);
        }
        .omnibox-input { display: flex; align-items: center; gap: 12px; padding: 14px 16px; }
        .omnibox-field {
          flex: 1; background: transparent; border: 0; outline: 0;
          color: var(--text); font-size: 16px; font-family: inherit; font-weight: 400;
        }
        .omnibox-field::placeholder { color: var(--text-subtle); }
        .omnibox-hint {
          display: flex; align-items: center;
          padding: 8px 16px 10px;
          border-top: 1px solid var(--border);
          font-size: 11.5px; color: var(--text-subtle); gap: 10px;
        }
        .section-head { display: flex; align-items: baseline; margin-bottom: 12px; gap: 10px; }
        .section-title {
          font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
          color: var(--text-muted); font-weight: 600; flex: 1;
        }
        .queue-row {
          display: flex; align-items: center; gap: 12px;
          padding: 10px 14px; background: var(--bg-1);
          border: 1px solid var(--border); border-radius: 8px;
        }
        .queue-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--accent); animation: pulse-q 1.6s ease-in-out infinite; flex-shrink: 0;
        }
        .queue-dot[data-stage="queued"] { background: var(--text-faint); animation: none; }
        .queue-dot[data-stage="failed"] { background: var(--danger); animation: none; }
        .queue-bar { height: 2px; background: var(--border); border-radius: 1px; margin-top: 6px; overflow: hidden; }
        .queue-bar > div { height: 100%; background: var(--accent); transition: width 300ms ease; }
        @keyframes pulse-q { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.4; transform:scale(1.4); } }
        .recent-row {
          display: flex; gap: 14px; padding: 14px; border-radius: 10px;
          transition: background var(--dur); cursor: pointer;
        }
        .recent-row:hover { background: var(--bg-1); }
        .recent-thumb {
          width: 44px; height: 44px; border-radius: 8px; background: var(--bg-2);
          display: grid; place-items: center; color: var(--text-muted); flex-shrink: 0;
          overflow: hidden;
        }
        .prompt-chip {
          display: flex; align-items: center; gap: 10px;
          padding: 12px 14px; border: 1px solid var(--border); border-radius: 8px;
          font-size: 13px; cursor: pointer; color: var(--text-muted); transition: all var(--dur);
        }
        .prompt-chip:hover { border-color: var(--border-accent); color: var(--text); background: var(--bg-1); }
      `}</style>
    </div>
  )
}
