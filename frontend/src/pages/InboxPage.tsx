import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Sidebar from '@/components/shared/Sidebar'
import Topbar from '@/components/shared/Topbar'
import Icons from '@/components/shared/Icons'
import SourcePill from '@/components/shared/SourcePill'
import { fetchTasks } from '@/api/tasks'
import { retryYouTube } from '@/api/youtube'
import type { Task } from '@/types'

function stageLabel(t: Task): string {
  if (t.status === 'queued') return 'queued'
  if (t.status === 'processing') return 'processing'
  if (t.status === 'completed') return 'done'
  if (t.status === 'failed') return 'failed'
  return t.status
}

function sourceType(t: Task): string {
  if (t.task_type?.includes('youtube')) return 'youtube'
  if (t.task_type?.includes('article')) return 'blog'
  if (t.task_type?.includes('reddit')) return 'reddit'
  return 'web'
}

export default function InboxPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => fetchTasks(50),
    refetchInterval: 3000,
  })

  const retryMutation = useMutation({
    mutationFn: (itemId: string) => retryYouTube(itemId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const inProgress = tasks.filter((t) => t.status === 'processing').length
  const done = tasks.filter((t) => t.status === 'completed').length
  const failed = tasks.filter((t) => t.status === 'failed').length
  const failedTasks = tasks.filter((t) => t.status === 'failed')

  return (
    <div className="artboard-root">
      <Sidebar active="inbox" />
      <div className="main">
        <Topbar
          crumbs={['Inbox']}
          actions={
            <>
              <button className="btn ghost"><Icons.settings /> Rules</button>
              <button className="btn primary" onClick={() => navigate('/youtube')}><Icons.plus /> Add source</button>
            </>
          }
        />
        <div className="page">
          <div className="page-narrow">
            <h1 className="page-title">Inbox <span className="dim">— the workshop</span></h1>
            <p className="page-subtitle">Everything you've added, mid-transformation. Re-tag, re-summarize, or dismiss.</p>

            {!isLoading && (
              <div style={{ display: 'flex', gap: 6, marginBottom: 16, alignItems: 'center', paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
                <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>
                  {inProgress} processing · {done} done · {failed} failed
                </span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                  {failedTasks.length > 0 && (
                    <button
                      className="btn ghost"
                      style={{ fontSize: 11.5 }}
                      onClick={() => {
                        failedTasks.forEach((t) => {
                          if (t.knowledge_item_id) retryMutation.mutate(t.knowledge_item_id)
                        })
                      }}
                    >
                      Retry failed
                    </button>
                  )}
                </div>
              </div>
            )}

            {isLoading && (
              <div style={{ color: 'var(--text-subtle)', fontSize: 13.5, padding: '24px 0' }}>Loading…</div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {tasks.map((t) => {
                const stage = stageLabel(t)
                const knowledgeId = t.knowledge_item_id ?? t.result?.knowledge_item_id
                return (
                  <div key={t.task_id} className={`inbox-card stage-${stage}`}>
                    <div className="inbox-stage"><div className="inbox-dot" /></div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                        <SourcePill type={sourceType(t)} />
                        <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{t.task_type}</span>
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 10 }}>
                        {t.message ?? t.task_type}
                      </div>
                      {stage !== 'done' && stage !== 'failed' && (
                        <div className="inbox-bar"><div style={{ width: `${t.progress}%` }} /></div>
                      )}
                      <div className="inbox-step">
                        {stage === 'done' ? 'ready · added to Library' : t.message ?? stage}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {stage === 'done' && knowledgeId && (
                        <button
                          className="btn ghost"
                          style={{ fontSize: 11 }}
                          onClick={() => navigate(`/inbox/review/${knowledgeId}`)}
                        >
                          Open →
                        </button>
                      )}
                      {stage === 'failed' && knowledgeId && (
                        <button
                          className="btn ghost"
                          style={{ fontSize: 11 }}
                          onClick={() => retryMutation.mutate(knowledgeId)}
                        >
                          Retry
                        </button>
                      )}
                      <button className="btn ghost" style={{ fontSize: 11, padding: '4px 6px' }}>
                        <Icons.close style={{ width: 12, height: 12 }} />
                      </button>
                    </div>
                  </div>
                )
              })}

              {!isLoading && tasks.length === 0 && (
                <div style={{ color: 'var(--text-subtle)', fontSize: 13.5, padding: '24px 0', textAlign: 'center' }}>
                  No tasks yet — add a source to get started.
                </div>
              )}
            </div>

            <div style={{ marginTop: 36 }}>
              <div style={{ fontSize: 12, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: 12 }}>
                Auto-ingest rules
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                <div className="rule-row" style={{ borderStyle: 'dashed', background: 'transparent', cursor: 'pointer' }}>
                  <Icons.plus style={{ width: 14, height: 14, color: 'var(--text-subtle)' }} />
                  <span style={{ fontSize: 12.5, color: 'var(--text-subtle)' }}>new rule — RSS, channel, subreddit, newsletter… (coming soon)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <style>{`
        .inbox-card {
          display: flex; gap: 14px; padding: 14px;
          background: var(--bg-1); border: 1px solid var(--border);
          border-radius: 10px; align-items: flex-start;
        }
        .inbox-stage { width: 24px; display: grid; place-items: center; padding-top: 6px; }
        .inbox-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--accent); animation: pulse-ib 1.6s ease-in-out infinite;
        }
        .stage-queued .inbox-dot { background: var(--text-faint); animation: none; }
        .stage-done .inbox-dot { background: var(--good); animation: none; }
        .stage-failed .inbox-dot { background: var(--danger); animation: none; }
        @keyframes pulse-ib { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:0.4; transform:scale(1.4); } }
        .inbox-bar { height: 2px; background: var(--border); border-radius: 1px; overflow: hidden; margin-bottom: 6px; }
        .inbox-bar > div { height: 100%; background: var(--accent); transition: width 300ms; }
        .inbox-step { font-family: var(--font-mono); font-size: 10.5px; color: var(--text-subtle); letter-spacing: 0.04em; }
        .stage-done .inbox-step { color: var(--good); }
        .stage-failed .inbox-step { color: var(--danger); }
        .rule-row {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 14px; border: 1px solid var(--border);
          border-radius: 8px; background: var(--bg-1);
        }
      `}</style>
    </div>
  )
}
