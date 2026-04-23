import { useState } from 'react'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { submitYouTube } from '@/api/youtube'
import { pollTask } from '@/api/tasks'
import type { Task } from '@/types'

type Stage = 'idle' | 'submitting' | 'processing' | 'done' | 'error'

export default function YouTubePage() {
  const [url, setUrl] = useState('')
  const [summaryLength, setSummaryLength] = useState('medium')
  const [stage, setStage] = useState<Stage>('idle')
  const [task, setTask] = useState<Task | null>(null)
  const [errorMsg, setErrorMsg] = useState('')

  const handleSubmit = async () => {
    if (!url.trim()) return
    setStage('submitting')
    setErrorMsg('')
    try {
      const res = await submitYouTube(url.trim(), summaryLength)
      setStage('processing')
      pollTask(
        res.task_id,
        (t) => setTask(t),
        (t) => { setTask(t); setStage('done') },
        (err) => { setErrorMsg(err); setStage('error') }
      )
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to submit')
      setStage('error')
    }
  }

  const reset = () => { setUrl(''); setStage('idle'); setTask(null); setErrorMsg('') }

  return (
    <div className="artboard-root">
      <Sidebar active="youtube" />
      <div className="main">
        <Topbar
          crumbs={['Sources', 'YouTube']}
          actions={stage !== 'idle' ? <button className="btn ghost" onClick={reset}>Start over</button> : undefined}
        />
        <div className="page">
          <div className="page-narrow">
            <h1 className="page-title">Ingest a YouTube video</h1>
            <p className="page-subtitle">Paste a URL — Merlin will fetch the transcript, summarize it, and propose tags.</p>

            {(stage === 'idle' || stage === 'error') && (
              <div className="yt-form">
                <div style={{ marginBottom: 20 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 8 }}>YouTube URL</label>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
                      <Icons.yt style={{ width: 16, height: 16, color: '#e0826a', flexShrink: 0 }} />
                      <input
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                        placeholder="https://youtube.com/watch?v=…"
                        style={{ flex: 1, background: 'transparent', border: 0, outline: 0, color: 'var(--text)', fontSize: 14, fontFamily: 'inherit' }}
                      />
                    </div>
                  </div>
                </div>

                <div style={{ marginBottom: 24 }}>
                  <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 8 }}>Summary length</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {['short', 'medium', 'long'].map((l) => (
                      <button
                        key={l}
                        className={`btn${summaryLength === l ? ' primary' : ' ghost'}`}
                        onClick={() => setSummaryLength(l)}
                        style={{ textTransform: 'capitalize' }}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {stage === 'error' && (
                  <div style={{ padding: '10px 14px', background: 'rgba(224,137,128,0.1)', border: '1px solid var(--danger)', borderRadius: 8, fontSize: 13, color: 'var(--danger)', marginBottom: 16 }}>
                    {errorMsg}
                  </div>
                )}

                <button
                  className="btn primary"
                  onClick={handleSubmit}
                  disabled={!url.trim()}
                  style={{ fontSize: 14, padding: '10px 24px' }}
                >
                  <Icons.arrowUp /> Ingest video
                </button>
              </div>
            )}

            {stage === 'submitting' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '20px 0' }}>
                <div className="spinner-lg" />
                <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>Submitting…</span>
              </div>
            )}

            {(stage === 'processing' || stage === 'done') && task && (
              <div style={{ marginTop: 8 }}>
                <div style={{ padding: '20px 24px', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 12, marginBottom: 20 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                    <SourcePill type="youtube" />
                    <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>task {task.task_id.slice(0, 8)}…</span>
                    <span className={`tag${stage === 'done' ? ' accent' : ''}`} style={{ marginLeft: 'auto' }}>
                      <span className="dot" style={{ background: stage === 'done' ? 'var(--accent)' : 'var(--good)' }} />
                      {task.status}
                    </span>
                  </div>

                  {stage === 'processing' && (
                    <>
                      <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginBottom: 10 }}>
                        <div style={{ height: '100%', background: 'var(--accent)', width: `${task.progress ?? 0}%`, transition: 'width 400ms' }} />
                      </div>
                      <div className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{task.message || 'Processing…'}</div>
                    </>
                  )}

                  {stage === 'done' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <Icons.check style={{ width: 18, height: 18, color: 'var(--good)' }} />
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 500 }}>Added to your Library</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{task.message || 'Ingestion complete'}</div>
                      </div>
                    </div>
                  )}
                </div>

                {stage === 'done' && (
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button className="btn primary" onClick={() => window.location.href = '/library'}>
                      <Icons.library /> View in Library
                    </button>
                    <button className="btn ghost" onClick={reset}>
                      <Icons.plus /> Ingest another
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tips */}
            {stage === 'idle' && (
              <div style={{ marginTop: 48 }}>
                <div style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 12 }}>Supported</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {[
                    { icon: Icons.yt, label: 'YouTube videos', desc: 'Transcript + summary + chapters' },
                    { icon: Icons.clock, label: 'Any length', desc: 'Short clips to 4-hour lectures' },
                    { icon: Icons.tag, label: 'Auto-tagging', desc: 'Merlin proposes relevant tags' },
                    { icon: Icons.chat, label: 'Chat-ready', desc: 'Ask questions about the video immediately' },
                  ].map(({ icon: Icon, label, desc }) => (
                    <div key={label} style={{ padding: '14px 16px', background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <Icon style={{ width: 16, height: 16, color: 'var(--accent)', marginTop: 2, flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{desc}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`
        .yt-form { max-width: 560px; }
        .spinner-lg {
          width: 20px; height: 20px;
          border: 2px solid var(--border-strong);
          border-top-color: var(--accent);
          border-radius: 50%;
          animation: spin-lg 0.9s linear infinite;
        }
        @keyframes spin-lg { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
