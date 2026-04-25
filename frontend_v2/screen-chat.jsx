/* global React, I, Sidebar, Topbar, SourcePill, ALL_SOURCES, TAGS */
const { useState: useStateChat } = React;

function ChatScreen() {
  const [ctx, setCtx] = useStateChat([
    { kind: 'tag', name: 'llm-research', color: '#c9a9ff', count: 34 },
    { kind: 'source', id: 'v1', title: 'Karpathy — State of GPT' },
  ]);
  const [input, setInput] = useStateChat('');

  const messages = [
    { role: 'user', text: "Across everything I've saved on llm-research, what are the 3 biggest disagreements between authors?" },
    {
      role: 'merlin',
      text: `Reading across 34 sources, here are the three biggest fault lines:

**1. RLHF: essential or a crutch?** Karpathy treats RLHF as a necessary alignment step; Chip Huyen argues DPO + careful SFT gets you 90% of the way without the instability. A third of your Reddit threads lean Huyen's way.

**2. Long context vs. retrieval.** Anthropic's papers in your vault lean long-context. A competing cluster (including two of your No Boilerplate videos) calls it "brute force laziness" and insists on structured retrieval.

**3. What counts as "reasoning".** Your saved Sutton lecture treats chain-of-thought as theatre. Two blogs you tagged 'fundamentals' disagree: they treat CoT as genuine computation unfolding.`,
      cites: [
        { type: 'youtube', label: 'State of GPT · 17:30' },
        { type: 'blog', label: 'Huyen · Building LLM Apps' },
        { type: 'reddit', label: 'r/LocalLLaMA discussion' },
        { type: 'blog', label: 'Sutton · The Bitter Lesson' },
      ],
    },
  ];

  return (
    <div className="artboard-root">
      <Sidebar active="chat" />
      <div className="main">
        <Topbar
          crumbs={['Chat', 'Cross-library analysis']}
          actions={
            <>
              <button className="btn ghost"><I.share /> Share thread</button>
              <button className="btn ghost"><I.plus /> New</button>
            </>
          }
        />

        <div className="chat-layout">
          {/* Context rail */}
          <div className="chat-ctx">
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 14 }}>Context</div>

            <div style={{ fontSize: 11.5, color: 'var(--text-subtle)', marginBottom: 8 }}>Merlin will answer using only these sources.</div>

            <div className="ctx-section">
              <div className="ctx-section-label">Tags</div>
              {ctx.filter(c => c.kind === 'tag').map(c => (
                <div key={c.name} className="ctx-item">
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color }} />
                  <span>{c.name}</span>
                  <span className="mono text-subtle" style={{ fontSize: 10.5, marginLeft: 'auto' }}>{c.count} sources</span>
                  <I.close style={{ width: 11, height: 11, color: 'var(--text-subtle)', cursor: 'pointer' }} />
                </div>
              ))}
              <button className="ctx-add">+ add tag</button>
            </div>

            <div className="ctx-section">
              <div className="ctx-section-label">Specific sources</div>
              {ctx.filter(c => c.kind === 'source').map(c => (
                <div key={c.id} className="ctx-item">
                  <I.yt style={{ width: 13, height: 13, color: 'var(--text-muted)' }} />
                  <span style={{ fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
                  <I.close style={{ width: 11, height: 11, color: 'var(--text-subtle)', cursor: 'pointer', marginLeft: 'auto' }} />
                </div>
              ))}
              <button className="ctx-add">+ add source</button>
            </div>

            <div className="ctx-section">
              <div className="ctx-section-label">Mode</div>
              <div className="mode-toggle">
                <button className="active">Library</button>
                <button>+ Web</button>
                <button>Model only</button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-subtle)', marginTop: 8, lineHeight: 1.5 }}>
                Merlin answers <b style={{ color: 'var(--text)' }}>only</b> from your vault — citations required.
              </div>
            </div>

            <div className="ctx-scope-stat">
              <div style={{ fontSize: 11, color: 'var(--text-subtle)' }}>scope</div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 28, lineHeight: 1, margin: '4px 0' }}>35</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>sources in context</div>
            </div>
          </div>

          {/* Chat column */}
          <div className="chat-main">
            <div className="chat-messages">
              {messages.map((m, i) => (
                <div key={i} className={"chat-msg chat-msg-" + m.role}>
                  {m.role === 'merlin' && <div className="chat-mark">✦</div>}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {m.role === 'user' && <div className="user-label">you</div>}
                    {m.role === 'merlin' && <div className="merlin-label">Merlin <span className="text-subtle mono" style={{ fontSize: 10.5, marginLeft: 8 }}>thought for 2.4s · 35 sources</span></div>}
                    <div className="chat-content" dangerouslySetInnerHTML={{ __html: m.text.replace(/\n\n/g, '</p><p>').replace(/^/, '<p>').replace(/$/, '</p>').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>') }} />
                    {m.cites && (
                      <div style={{ marginTop: 16 }}>
                        <div className="mono" style={{ fontSize: 10, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Sources</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
                          {m.cites.map((c, j) => (
                            <div key={j} className="source-cite">
                              <SourcePill type={c.type} />
                              <span style={{ fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="chat-input-wrap">
              <div className="chat-input-box">
                <textarea
                  rows={2}
                  placeholder="Ask Merlin anything about your library…"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                />
                <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
                  <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>
                    ⌘↵ to send · / for commands
                  </span>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                    <button className="btn ghost" style={{ padding: '4px 8px', fontSize: 11.5 }}><I.link style={{width:11,height:11}}/> attach</button>
                    <button className="btn primary" style={{ padding: '4px 10px' }}><I.arrowUp style={{width:12,height:12}}/></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .chat-layout {
          flex: 1; min-height: 0;
          display: grid;
          grid-template-columns: 280px 1fr;
          overflow: hidden;
        }
        .chat-ctx {
          padding: 22px 20px;
          border-right: 1px solid var(--border);
          overflow-y: auto;
          background: var(--bg-1);
        }
        .ctx-section { margin-bottom: 22px; }
        .ctx-section-label {
          font-size: 11px;
          color: var(--text-muted);
          margin-bottom: 8px;
          font-weight: 500;
        }
        .ctx-item {
          display: flex; align-items: center; gap: 8px;
          padding: 7px 10px;
          border-radius: 6px;
          background: var(--bg-2);
          border: 1px solid var(--border);
          font-size: 12.5px;
          margin-bottom: 4px;
        }
        .ctx-add {
          width: 100%;
          background: transparent;
          border: 1px dashed var(--border-strong);
          border-radius: 6px;
          padding: 6px;
          color: var(--text-subtle);
          font-family: inherit;
          font-size: 11.5px;
          cursor: pointer;
          margin-top: 4px;
        }
        .ctx-add:hover { color: var(--text); border-color: var(--border-accent); }

        .mode-toggle {
          display: grid; grid-template-columns: 1fr 1fr 1fr;
          background: var(--bg-2);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 2px;
          gap: 2px;
        }
        .mode-toggle button {
          background: transparent; border: 0;
          padding: 5px;
          font-size: 11px;
          color: var(--text-muted);
          cursor: pointer;
          border-radius: 4px;
          font-family: inherit;
        }
        .mode-toggle button.active {
          background: var(--bg-3);
          color: var(--text);
        }

        .ctx-scope-stat {
          margin-top: 40px;
          padding-top: 20px;
          border-top: 1px solid var(--border);
        }

        .chat-main {
          display: flex; flex-direction: column;
          min-width: 0;
        }
        .chat-messages {
          flex: 1; overflow-y: auto;
          padding: 36px 0 28px;
        }
        .chat-msg {
          display: flex; gap: 14px;
          max-width: 780px;
          margin: 0 auto 32px;
          padding: 0 32px;
        }
        .user-label, .merlin-label {
          font-size: 11px;
          color: var(--text-subtle);
          text-transform: lowercase;
          letter-spacing: 0.04em;
          margin-bottom: 6px;
          font-weight: 500;
        }
        .merlin-label { color: var(--accent); }
        .chat-mark {
          width: 24px; height: 24px;
          color: var(--accent);
          font-family: var(--font-display);
          font-size: 22px;
          font-style: italic;
          line-height: 1;
          flex-shrink: 0;
        }
        .chat-msg-user .chat-content {
          font-size: 15px;
          color: var(--text);
          line-height: 1.55;
        }
        .chat-msg-user {
          padding-left: 68px;
        }
        .chat-content p {
          font-size: 14.5px;
          line-height: 1.7;
          margin: 0 0 12px;
          color: var(--text);
        }
        .chat-content p:last-child { margin-bottom: 0; }

        .source-cite {
          display: flex; align-items: center; gap: 8px;
          padding: 8px 10px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 6px;
          cursor: pointer;
          transition: border-color var(--dur);
        }
        .source-cite:hover { border-color: var(--border-accent); }

        .chat-input-wrap {
          padding: 16px 32px 24px;
          border-top: 1px solid var(--border);
          background: var(--bg);
        }
        .chat-input-box {
          max-width: 780px;
          margin: 0 auto;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 12px;
          overflow: hidden;
          transition: border-color var(--dur);
        }
        .chat-input-box:focus-within { border-color: var(--border-accent); }
        .chat-input-box textarea {
          width: 100%;
          background: transparent;
          border: 0;
          outline: 0;
          color: var(--text);
          font-family: inherit;
          font-size: 14px;
          padding: 14px 16px;
          resize: none;
          line-height: 1.5;
        }
        .chat-input-box textarea::placeholder { color: var(--text-subtle); }
      `}</style>
    </div>
  );
}

window.ChatScreen = ChatScreen;
