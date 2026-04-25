/* global React, I, Sidebar, Topbar, SourcePill, VIDEOS, TAGS */
const { useState: useStateYt } = React;

function YoutubeScreen() {
  const v = VIDEOS[0];
  const [tab, setTab] = useStateYt('summary');
  const [chatInput, setChatInput] = useStateYt('');
  const [messages, setMessages] = useStateYt([
    { role: 'user', text: 'At what timestamp does he talk about RLHF vs SFT trade-offs?' },
    { role: 'merlin', text: "Around **17:30**, Karpathy frames SFT as giving the model a 'persona' and RLHF as aligning it with *preferences*. He argues RLHF is harder than it looks because reward models are imperfect proxies — quoting: 'you're optimizing a noisy signal of what humans want.'", cites: [{ t: '17:30', label: 'Supervised fine-tuning vs RLHF' }, { t: '19:02', label: '~1m later' }] },
    { role: 'user', text: 'Does this contradict the Huyen blog I saved last week?' },
    { role: 'merlin', text: "Partially. Chip Huyen's *Building LLM Applications for Production* agrees that reward hacking is real, but is more bullish on DPO as a practical alternative. Karpathy doesn't mention DPO in this talk.", cites: [{ type: 'blog', label: 'Building LLM Applications for Production' }] },
  ]);

  return (
    <div className="artboard-root">
      <Sidebar active="youtube" />
      <div className="main">
        <Topbar
          crumbs={['Library', 'YouTube', v.title.slice(0, 40) + '…']}
          actions={
            <>
              <button className="btn ghost"><I.share /> Share</button>
              <button className="btn ghost"><I.tag /> Tag</button>
              <button className="btn ghost"><I.paper /> Export</button>
            </>
          }
        />
        <div className="yt-layout">
          {/* LEFT — video + metadata */}
          <div className="yt-left">
            <div className="yt-player img-ph" style={{ aspectRatio: '16/9' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(0,0,0,0.4)', display: 'grid', placeItems: 'center' }}>
                  <I.yt style={{ width: 28, height: 28, color: '#fff' }} />
                </div>
                <div className="mono" style={{ color: 'var(--text-subtle)' }}>video player</div>
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <SourcePill type="youtube" />
                <span className="text-subtle mono" style={{ fontSize: 11 }}>{v.duration}</span>
                <span className="text-subtle mono" style={{ fontSize: 11 }}>·</span>
                <span className="text-subtle mono" style={{ fontSize: 11 }}>{v.views} views</span>
              </div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 26, lineHeight: 1.15, margin: '0 0 8px', fontWeight: 400, letterSpacing: '-0.01em' }}>{v.title}</h2>
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>{v.channel}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
                {v.tags.map(t => <span key={t} className="tag"><span className="dot" style={{ background: TAGS.find(x=>x.name===t)?.color || '#999'}}/>{t}</span>)}
                <span className="tag" style={{ cursor: 'pointer', borderStyle: 'dashed' }}><I.plus style={{ width: 10, height: 10 }} /> add tag</span>
              </div>
            </div>

            <div className="divider" />

            {/* Tabs */}
            <div className="yt-tabs">
              {['summary', 'topics', 'transcript'].map(t => (
                <button key={t} className={"yt-tab" + (tab === t ? ' is-active' : '')} onClick={() => setTab(t)}>
                  {t}
                </button>
              ))}
            </div>

            {tab === 'summary' && (
              <div style={{ marginTop: 16 }}>
                <p style={{ fontSize: 14.5, lineHeight: 1.65, color: 'var(--text)', marginBottom: 16 }}>
                  {v.summary}
                </p>
                <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, padding: 14 }}>
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>Key takeaways</div>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.7, color: 'var(--text-muted)' }}>
                    <li>Pretraining is compression — intelligence emerges from lossy next-token prediction</li>
                    <li>Base models aren't assistants; they're document completers forced into Q&A shape</li>
                    <li>RLHF optimizes a noisy proxy — useful, but not the whole story</li>
                    <li>Tools and retrieval are how we add 'System 2' to 'System 1' models</li>
                  </ul>
                </div>
              </div>
            )}

            {tab === 'topics' && (
              <div style={{ marginTop: 16, display: 'grid', gap: 8 }}>
                {v.topics.map((t, i) => (
                  <div key={i} className="topic-row">
                    <span className="mono topic-time">{t.t}</span>
                    <span>{t.text}</span>
                    <I.arrowUp style={{ width: 12, height: 12, marginLeft: 'auto', transform: 'rotate(45deg)', color: 'var(--text-subtle)' }} />
                  </div>
                ))}
              </div>
            )}

            {tab === 'transcript' && (
              <div style={{ marginTop: 16, fontSize: 13.5, lineHeight: 1.7, color: 'var(--text-muted)' }}>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>Full transcript · english</div>
                <p><span className="mono topic-time" style={{ marginRight: 8 }}>00:04</span> Hello everyone, I'm excited to be here. This talk is going to be about the current state of GPT, and more generally, about the rapidly growing ecosystem of large language models…</p>
                <p><span className="mono topic-time" style={{ marginRight: 8 }}>00:32</span> Let me start with what I think is the most important diagram in the field right now, which divides the training pipeline into four stages…</p>
              </div>
            )}

            {/* Top comments — pulled from YouTube */}
            <div className="divider" />
            <div className="section-head-yt">
              <span className="section-title-yt">Top comments <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>from YouTube · 2.4k total</span></span>
              <button className="btn ghost" style={{ fontSize: 11 }}>Most upvoted ▾</button>
            </div>
            <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
              {[
                { who: '@jeremyhoward', when: '2y ago', ups: '4.2k', text: "This is the clearest 40 minutes on LLMs I've seen anywhere. The System 1 / System 2 framing made something click that 3 papers didn't." },
                { who: '@alexishouse', when: '2y ago', ups: '1.8k', text: "The bit at 26:02 about 'prompt engineering as System 2 scaffolding' is quietly the thesis of the whole talk." },
                { who: '@mkolden', when: '11mo ago', ups: '612', text: "Re-watching after a year and now half the things he calls open problems have preprints. Wild pace." },
              ].map((c, i) => (
                <div key={i} className="yt-comment">
                  <div className="yt-comment-avatar">{c.who[1].toUpperCase()}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 500 }}>{c.who}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{c.when}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', marginLeft: 'auto' }}>▲ {c.ups}</span>
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.55 }}>{c.text}</div>
                  </div>
                </div>
              ))}
              <button className="btn ghost" style={{ justifyContent: 'center', fontSize: 11.5 }}>+ Merlin synthesized comments into 3 themes</button>
            </div>
          </div>

          {/* RIGHT — Chat with this video */}
          <div className="yt-right">
            <div className="yt-chat-head">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <I.sparkle style={{ width: 14, height: 14, color: 'var(--accent)' }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>Chat with this video</span>
              </div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>context: 1 video</div>
            </div>

            <div className="yt-chat-body">
              {messages.map((m, i) => (
                <div key={i} className={"msg msg-" + m.role}>
                  {m.role === 'merlin' && <div className="msg-mark">✦</div>}
                  <div className="msg-bubble">
                    <div style={{ fontSize: 13.5, lineHeight: 1.55 }} dangerouslySetInnerHTML={{ __html: m.text.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '<i>$1</i>') }} />
                    {m.cites && (
                      <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                        {m.cites.map((c, j) => (
                          <span key={j} className="cite">
                            {c.type === 'blog' ? <I.paper style={{ width: 10, height: 10 }} /> : <I.clock style={{ width: 10, height: 10 }} />}
                            {c.t || ''} {c.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="yt-chat-input">
              <div className="context-bar">
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>context:</span>
                <span className="context-chip"><I.yt style={{width:10,height:10}}/> this video <I.close style={{width:10,height:10,opacity:0.5}}/></span>
                <span className="context-chip add">+ add tag · blog · or video</span>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <textarea
                  className="input"
                  rows={2}
                  placeholder="Ask about this video, or bring in more context…"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  style={{ resize: 'none' }}
                />
                <button className="btn primary" style={{ height: 36 }}><I.arrowUp /></button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .yt-layout {
          flex: 1; min-height: 0;
          display: grid;
          grid-template-columns: 1fr 420px;
          overflow: hidden;
        }
        .yt-left {
          padding: 28px 32px;
          overflow-y: auto;
          border-right: 1px solid var(--border);
        }
        .yt-player {
          position: relative;
          border-radius: 12px;
          overflow: hidden;
          display: grid; place-items: center;
        }
        .yt-tabs {
          display: flex; gap: 2px;
          border-bottom: 1px solid var(--border);
        }
        .yt-tab {
          background: transparent; border: 0;
          padding: 10px 14px;
          color: var(--text-muted);
          font-size: 12.5px;
          font-family: inherit;
          text-transform: capitalize;
          cursor: pointer;
          border-bottom: 2px solid transparent;
          margin-bottom: -1px;
          font-weight: 500;
          letter-spacing: 0.02em;
        }
        .yt-tab.is-active {
          color: var(--text);
          border-bottom-color: var(--accent);
        }

        .topic-row {
          display: flex; align-items: center; gap: 14px;
          padding: 10px 14px;
          border-radius: 8px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          cursor: pointer;
          transition: all var(--dur);
          font-size: 13.5px;
        }
        .topic-row:hover { border-color: var(--border-accent); background: var(--bg-2); }
        .topic-time {
          color: var(--accent);
          font-size: 11.5px;
          min-width: 44px;
        }

        .yt-right {
          display: flex; flex-direction: column;
          min-width: 0;
          background: var(--bg-1);
        }
        .yt-chat-head {
          display: flex; align-items: center; justify-content: space-between;
          padding: 14px 18px;
          border-bottom: 1px solid var(--border);
        }
        .yt-chat-body {
          flex: 1;
          overflow-y: auto;
          padding: 18px;
          display: flex; flex-direction: column; gap: 18px;
        }
        .msg { display: flex; gap: 10px; }
        .msg-user { justify-content: flex-end; }
        .msg-user .msg-bubble {
          background: var(--bg-3);
          border: 1px solid var(--border);
          border-radius: 12px 12px 2px 12px;
          padding: 10px 14px;
          max-width: 85%;
        }
        .msg-merlin .msg-bubble {
          max-width: 100%;
          padding: 0;
          color: var(--text);
        }
        .msg-mark {
          width: 22px; height: 22px;
          flex-shrink: 0;
          color: var(--accent);
          font-family: var(--font-display);
          font-size: 18px;
          line-height: 1;
          font-style: italic;
        }
        .cite {
          display: inline-flex; align-items: center; gap: 4px;
          font-family: var(--font-mono);
          font-size: 10.5px;
          padding: 2px 7px;
          background: var(--accent-soft);
          color: var(--accent);
          border-radius: 4px;
          cursor: pointer;
          border: 1px solid var(--border-accent);
        }
        .yt-chat-input {
          border-top: 1px solid var(--border);
          padding: 12px 14px 14px;
          background: var(--bg);
        }
        .context-bar {
          display: flex; align-items: center; gap: 6px;
          margin-bottom: 10px;
          flex-wrap: wrap;
        }
        .context-chip {
          display: inline-flex; align-items: center; gap: 5px;
          padding: 3px 8px;
          border-radius: 14px;
          background: var(--bg-2);
          border: 1px solid var(--border);
          font-size: 11px;
          color: var(--text-muted);
        }
        .context-chip.add {
          border-style: dashed;
          cursor: pointer;
          color: var(--text-subtle);
        }
        .section-head-yt { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
        .section-title-yt {
          font-size: 12px; letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--text-muted); font-weight: 600; flex: 1;
        }
        .yt-comment {
          display: flex; gap: 12px;
          padding: 12px 14px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 8px;
        }
        .yt-comment-avatar {
          width: 26px; height: 26px; border-radius: 50%;
          background: var(--accent-soft); color: var(--accent);
          display: grid; place-items: center;
          font-size: 11px; font-weight: 600;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}

window.YoutubeScreen = YoutubeScreen;
