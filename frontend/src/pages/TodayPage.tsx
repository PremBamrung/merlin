import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { ALL_SOURCES, TAGS } from '@/data/mockData'

export default function TodayPage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [focused, setFocused] = useState(false)
  const [queue, setQueue] = useState([
    { url: 'youtube.com/watch?v=...', title: 'The State of GPT — A. Karpathy', stage: 'summarizing', pct: 72 },
    { url: 'huyenchip.com/...', title: 'Building LLM apps for production', stage: 'extracting', pct: 34 },
    { url: 'reddit.com/r/LocalLLaMA/...', title: 'What setups are you running...', stage: 'queued', pct: 0 },
  ])

  const hint = input.trim() === ''
    ? 'Paste a link, drop a YouTube URL, or ask Merlin about your library…'
    : /https?:\/\/|youtu|\.com\/|\.org\//.test(input)
      ? 'Press ↵ to ingest this source'
      : 'Press ↵ to ask your library'

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && input.trim()) {
      setQueue([{ url: input.slice(0, 40) + '…', title: 'New source', stage: 'queued', pct: 0 }, ...queue])
      setInput('')
    }
  }

  return (
    <div className="artboard-root">
      <Sidebar active="today" />
      <div className="main">
        <Topbar crumbs={['Home', 'Today']} />
        <div className="page">
          <div className="page-narrow">
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
                <span className="mono" style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                </span>
                <span className="text-subtle">·</span>
                <span className="text-subtle mono" style={{ fontSize: 11 }}>11 sources added this week</span>
              </div>
              <h1 className="page-title">Good morning. <span className="dim">What are we learning?</span></h1>
            </div>

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
                />
                <button className="btn primary" disabled={!input.trim()}>
                  <Icons.arrowUp /> Send
                </button>
              </div>
              <div className="omnibox-hint">
                <span>{hint}</span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>accepts</span>
                  <SourcePill type="youtube" />
                  <SourcePill type="blog" />
                  <SourcePill type="reddit" />
                  <SourcePill type="web" />
                </div>
              </div>
            </div>

            {/* Queue */}
            {queue.length > 0 && (
              <div style={{ marginTop: 28 }}>
                <div className="section-head">
                  <span className="section-title">Ingesting</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{queue.length} in queue</span>
                </div>
                <div style={{ display: 'grid', gap: 8 }}>
                  {queue.map((q, i) => (
                    <div key={i} className="queue-row">
                      <div className="queue-dot" data-stage={q.stage} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 13.5, fontWeight: 500 }}>{q.title}</span>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{q.url}</span>
                        </div>
                        <div className="queue-bar"><div style={{ width: `${q.pct}%` }} /></div>
                      </div>
                      <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {q.stage}
                      </span>
                    </div>
                  ))}
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
                {ALL_SOURCES.slice(0, 4).map((s) => (
                  <div key={s.id} className="recent-row">
                    <div className="recent-thumb">
                      {s.type === 'youtube' && <Icons.yt style={{ width: 20, height: 20 }} />}
                      {s.type === 'blog' && <Icons.paper style={{ width: 20, height: 20 }} />}
                      {s.type === 'reddit' && <Icons.reddit style={{ width: 20, height: 20 }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
                        <SourcePill type={s.type} />
                        <span className="text-subtle" style={{ fontSize: 11 }}>
                          {'channel' in s ? s.channel : 'author' in s ? s.author : 'subreddit' in s ? s.subreddit : ''}
                        </span>
                        <span className="text-subtle">·</span>
                        <span className="text-subtle mono" style={{ fontSize: 10.5 }}>{s.added}</span>
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{s.title}</div>
                      <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.45, display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' } as React.CSSProperties}>
                        {s.summary}
                      </div>
                      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                        {s.tags.map((t) => (
                          <span key={t} className="tag">
                            <span className="dot" style={{ background: TAGS.find((x) => x.name === t)?.color || '#999' }} />
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
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
                  <div key={i} className="prompt-chip" onClick={() => navigate('/chat')}>
                    <Icons.chat style={{ width: 14, height: 14, color: 'var(--accent)', flexShrink: 0 }} />
                    <span>{q}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
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
