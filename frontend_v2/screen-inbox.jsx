/* global React, I, Sidebar, Topbar, SourcePill, TAGS */
const { useState: useStateInbox } = React;

function InboxScreen() {
  const items = [
    { id: 1, url: 'youtube.com/watch?v=bZQun8Y4L2A', title: 'State of GPT — Andrej Karpathy', type: 'youtube', stage: 'summarizing', pct: 78, step: 'generating summary · medium length' },
    { id: 2, url: 'huyenchip.com/2023/04/11/llm-engineering.html', title: 'Building LLM Apps for Production', type: 'blog', stage: 'extracting', pct: 42, step: 'extracting readable content' },
    { id: 3, url: 'reddit.com/r/PKMS/comments/xyz...', title: 'What setups are you running for a second brain?', type: 'reddit', stage: 'queued', pct: 0, step: 'waiting' },
    { id: 4, url: 'youtube.com/watch?v=kCc8FmEb1nY', title: "Let's build GPT from scratch", type: 'youtube', stage: 'done', pct: 100, step: 'ready · added to Library' },
    { id: 5, url: 'reddit.com/r/LocalLLaMA/comments/abc', title: 'Benchmarks: Llama-3 vs Qwen-3', type: 'reddit', stage: 'failed', pct: 0, step: 'rate limited · retry' },
  ];

  return (
    <div className="artboard-root">
      <Sidebar active="inbox" />
      <div className="main">
        <Topbar crumbs={['Inbox']} actions={
          <>
            <button className="btn ghost"><I.settings/> Rules</button>
            <button className="btn primary"><I.plus/> Paste link</button>
          </>
        }/>
        <div className="page">
          <div className="page-narrow">
            <h1 className="page-title">Inbox <span className="dim">— the workshop</span></h1>
            <p className="page-subtitle">Everything you've dumped in, mid-transformation. Re-tag, re-summarize, or dismiss.</p>

            {/* Bulk actions */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16, alignItems: 'center', paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>3 in progress · 1 done · 1 failed</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                <button className="btn ghost" style={{ fontSize: 11.5 }}>Retry failed</button>
                <button className="btn ghost" style={{ fontSize: 11.5 }}>Approve all</button>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {items.map(it => (
                <div key={it.id} className={"inbox-card stage-" + it.stage}>
                  <div className="inbox-stage">
                    <div className="inbox-dot" />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                      <SourcePill type={it.type} />
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{it.url}</span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 10 }}>{it.title}</div>
                    {it.stage !== 'done' && it.stage !== 'failed' && (
                      <div className="inbox-bar"><div style={{ width: `${it.pct}%` }} /></div>
                    )}
                    <div className="inbox-step">{it.step}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {it.stage === 'done' && <button className="btn ghost" style={{ fontSize: 11 }}>Open →</button>}
                    {it.stage === 'failed' && <button className="btn ghost" style={{ fontSize: 11 }}>Retry</button>}
                    <button className="btn ghost" style={{ fontSize: 11, padding: '4px 6px' }}><I.close style={{width:12,height:12}}/></button>
                  </div>
                </div>
              ))}
            </div>

            {/* Auto-rules */}
            <div style={{ marginTop: 36 }}>
              <div className="section-head-inbox">Auto-ingest rules</div>
              <div style={{ display: 'grid', gap: 8 }}>
                <div className="rule-row">
                  <I.reddit style={{width:16,height:16,color:'var(--text-muted)'}}/>
                  <span style={{ fontSize: 13 }}>r/LocalLLaMA · top posts this week</span>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 'auto' }}>every Monday · 9am</span>
                  <span className="tag accent"><span className="dot"/>on</span>
                </div>
                <div className="rule-row">
                  <I.yt style={{width:16,height:16,color:'var(--text-muted)'}}/>
                  <span style={{ fontSize: 13 }}>YouTube · "Andrej Karpathy" uploads</span>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 'auto' }}>realtime</span>
                  <span className="tag accent"><span className="dot"/>on</span>
                </div>
                <div className="rule-row dashed">
                  <I.plus style={{width:14,height:14,color:'var(--text-subtle)'}}/>
                  <span style={{ fontSize: 12.5, color: 'var(--text-subtle)' }}>new rule — RSS, channel, subreddit, newsletter…</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .inbox-card {
          display: flex; gap: 14px;
          padding: 14px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 10px;
          align-items: flex-start;
        }
        .inbox-stage {
          width: 24px; display: grid; place-items: center; padding-top: 6px;
        }
        .inbox-dot {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--accent);
          animation: pulse-inbox 1.6s ease-in-out infinite;
        }
        .stage-queued .inbox-dot { background: var(--text-faint); animation: none; }
        .stage-done .inbox-dot { background: var(--good); animation: none; }
        .stage-failed .inbox-dot { background: var(--danger); animation: none; }
        @keyframes pulse-inbox {
          0%,100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(1.4); }
        }
        .inbox-bar {
          height: 2px; background: var(--border); border-radius: 1px;
          overflow: hidden; margin-bottom: 6px;
        }
        .inbox-bar > div { height: 100%; background: var(--accent); transition: width 300ms; }
        .stage-done .inbox-bar > div { background: var(--good); }
        .inbox-step {
          font-family: var(--font-mono);
          font-size: 10.5px;
          color: var(--text-subtle);
          text-transform: lowercase;
          letter-spacing: 0.04em;
        }
        .stage-done .inbox-step { color: var(--good); }
        .stage-failed .inbox-step { color: var(--danger); }

        .section-head-inbox {
          font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
          color: var(--text-muted); font-weight: 600; margin-bottom: 12px;
        }
        .rule-row {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 14px;
          border: 1px solid var(--border);
          border-radius: 8px;
          background: var(--bg-1);
        }
        .rule-row.dashed {
          border-style: dashed;
          background: transparent;
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}

window.InboxScreen = InboxScreen;
