/* global React, I, Sidebar, Topbar, SourcePill, TAGS */
function RedditScreen() {
  return (
    <div className="artboard-root">
      <Sidebar active="reddit" />
      <div className="main">
        <Topbar crumbs={['Library', 'Reddit', 'r/PKMS discussion']}
          actions={<>
            <button className="btn ghost"><I.share/> Share</button>
            <button className="btn ghost"><I.tag/> Tag</button>
          </>}/>
        <div className="page">
          <div style={{ maxWidth: 820, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
              <SourcePill type="reddit"/>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>r/PKMS · 182 comments · posted 5h ago · ▲ 847</span>
            </div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 34, lineHeight: 1.1, margin: '0 0 8px', fontWeight: 400 }}>
              What setups are you running for a local-first second brain in 2026?
            </h1>
            <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>u/second_brain_curious · self-post</div>

            {/* Merlin summary */}
            <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 28 }}>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <I.sparkle style={{width:12,height:12}}/> Thread synthesis
              </div>
              <p style={{ fontSize: 15, lineHeight: 1.65, margin: '0 0 12px' }}>
                Thread consensus: <b>local SQLite + embedding index, synced via Syncthing.</b> Obsidian vaults still dominate, but a growing minority is rolling their own Streamlit/FastAPI frontends — exactly the direction you're moving in.
              </p>
              <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-muted)', margin: 0 }}>
                Contentious points: whether Notion counts as "local" (it doesn't, per the top 3 comments), and whether chunking strategy matters more than embedding model choice (split 60/40).
              </p>
            </div>

            {/* Suggested tags — auto from Merlin */}
            <div className="auto-tag-box">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <I.sparkle style={{width:12,height:12,color:'var(--accent)'}}/>
                <span className="mono" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--text-muted)' }}>Suggested tags</span>
                <span className="text-subtle" style={{ fontSize: 11, marginLeft: 'auto' }}>Merlin proposed these while ingesting</span>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span className="tag accent"><span className="dot"/>pkm <I.check style={{width:10,height:10,marginLeft:2}}/></span>
                <span className="tag accent"><span className="dot"/>local-first <I.check style={{width:10,height:10,marginLeft:2}}/></span>
                <span className="suggest-tag">+ sqlite</span>
                <span className="suggest-tag">+ embeddings</span>
                <span className="suggest-tag">+ obsidian</span>
                <span className="suggest-tag-manual">+ add your own</span>
              </div>
            </div>

            <div className="section-head-rd">
              <span className="section-title-rd">Top comments <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>by upvotes</span></span>
              <button className="btn ghost" style={{ fontSize: 11 }}>Top ▾</button>
            </div>

            <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
              {[
                { who: 'u/vault_hermit', ups: '412', time: '4h', text: "SQLite + sqlite-vss for embeddings, Syncthing for device sync. Moved off Notion two years ago and never looked back. The moment your PKM is offline, everything feels different." },
                { who: 'u/markdown_maximalist', ups: '298', time: '3h', text: "Obsidian + Dataview + local Ollama for chat. The killer feature is chat *about your notes*, not just generic chat. Been rolling my own RAG glue — crude but works.", reply: true },
                { who: 'u/streamlit_refugee', ups: '187', time: '2h', text: "Built a Streamlit app for this exact purpose. Worked for 6 months then I hit a wall — Streamlit is wrong for daily-driver UIs. Migrating to FastAPI + a proper frontend this month." },
              ].map((c, i) => (
                <div key={i} className="rd-comment" style={{ marginLeft: c.reply ? 28 : 0 }}>
                  <div className="rd-score">
                    <svg viewBox="0 0 12 12" style={{width:10,height:10}}><path d="M6 2 L10 8 L2 8 Z" fill="var(--accent)"/></svg>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>{c.ups}</span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                      <span style={{ fontSize: 12.5, fontWeight: 500 }}>{c.who}</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>· {c.time}</span>
                    </div>
                    <div style={{ fontSize: 13.5, color: 'var(--text)', lineHeight: 1.55 }}>{c.text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <style>{`
        .auto-tag-box {
          background: var(--bg-1);
          border: 1px dashed var(--border-accent);
          border-radius: 10px;
          padding: 14px 16px;
          margin-bottom: 28px;
        }
        .suggest-tag {
          display: inline-flex; align-items: center; gap: 4px;
          font-size: 11px; padding: 2px 8px;
          border-radius: 20px;
          background: transparent;
          border: 1px dashed var(--border-strong);
          color: var(--text-muted);
          cursor: pointer;
        }
        .suggest-tag:hover { border-color: var(--accent); color: var(--accent); }
        .suggest-tag-manual {
          font-size: 11px; color: var(--text-subtle);
          padding: 2px 8px;
          cursor: pointer;
        }
        .section-head-rd { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
        .section-title-rd {
          font-size: 12px; letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--text-muted); font-weight: 600; flex: 1;
        }
        .rd-comment {
          display: flex; gap: 12px;
          padding: 14px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-left: 2px solid var(--border-strong);
          border-radius: 8px;
        }
        .rd-score {
          display: flex; flex-direction: column; align-items: center; gap: 2px;
          padding-top: 2px;
        }
      `}</style>
    </div>
  );
}

// Agentic chat with MCP/tools
function AgenticChatScreen() {
  return (
    <div className="artboard-root">
      <Sidebar active="chat" />
      <div className="main">
        <Topbar crumbs={['Chat', 'Agentic session']}
          actions={<>
            <button className="btn ghost"><I.share/> Share</button>
            <button className="btn primary"><I.plus/> New</button>
          </>}/>
        <div className="chat-layout-ag">
          {/* Tool rail */}
          <div className="chat-tool-rail">
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 14 }}>Tools & MCP</div>

            <div className="tool-section">
              <div className="tool-head">Library <span className="mono" style={{ fontSize: 10, color: 'var(--text-subtle)' }}>internal</span></div>
              {[
                { n: 'search_vault', d: 'semantic search your sources' },
                { n: 'fetch_summary', d: 'read a summarized doc' },
                { n: 'cluster_insight', d: 'analyze a tag cluster' },
              ].map(t => (
                <div key={t.n} className="tool-row enabled">
                  <span className="tool-dot"/>
                  <div style={{ flex: 1 }}>
                    <div className="tool-name">{t.n}</div>
                    <div className="tool-desc">{t.d}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="tool-section">
              <div className="tool-head">External <span className="mono" style={{ fontSize: 10, color: 'var(--text-subtle)' }}>MCP</span></div>
              {[
                { n: 'web_search', d: 'DuckDuckGo · LangChain', on: true },
                { n: 'youtube_fetch', d: 'transcript + metadata', on: true },
                { n: 'reddit_fetch', d: 'posts + top comments', on: true },
                { n: 'github_mcp', d: 'repos, issues, files', on: false },
                { n: 'linear_mcp', d: 'your workspace', on: false },
              ].map(t => (
                <div key={t.n} className={"tool-row" + (t.on ? ' enabled' : '')}>
                  <span className="tool-dot"/>
                  <div style={{ flex: 1 }}>
                    <div className="tool-name">{t.n}</div>
                    <div className="tool-desc">{t.d}</div>
                  </div>
                  <div className={"toggle" + (t.on ? ' on' : '')}><span/></div>
                </div>
              ))}
              <button className="ctx-add">+ connect MCP server</button>
            </div>
          </div>

          {/* Chat */}
          <div className="chat-main">
            <div className="chat-messages">
              <div className="chat-msg chat-msg-user" style={{ paddingLeft: 68 }}>
                <div style={{ flex: 1 }}>
                  <div className="user-label">you</div>
                  <div style={{ fontSize: 15, lineHeight: 1.6 }}>
                    Compare what my saved sources say about RLHF with what r/LocalLLaMA posted this week. Flag disagreements.
                  </div>
                </div>
              </div>

              <div className="chat-msg chat-msg-merlin">
                <div className="chat-mark">✦</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="merlin-label">Merlin <span className="text-subtle mono" style={{ fontSize: 10.5, marginLeft: 8 }}>thinking…</span></div>

                  {/* Tool trace */}
                  <div className="tool-trace">
                    <div className="trace-step done">
                      <I.check style={{width:11,height:11}}/>
                      <span className="mono" style={{ fontSize: 11 }}>search_vault</span>
                      <span className="trace-args mono">tag: "llm-research" · query: "RLHF"</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 'auto' }}>12 results · 0.4s</span>
                    </div>
                    <div className="trace-step done">
                      <I.check style={{width:11,height:11}}/>
                      <span className="mono" style={{ fontSize: 11 }}>reddit_fetch</span>
                      <span className="trace-args mono">r/LocalLLaMA · 7d · top</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 'auto' }}>8 posts · 1.2s</span>
                    </div>
                    <div className="trace-step running">
                      <div className="spinner"/>
                      <span className="mono" style={{ fontSize: 11 }}>fetch_summary</span>
                      <span className="trace-args mono">karpathy-state-of-gpt.md</span>
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)', marginLeft: 'auto' }}>reading…</span>
                    </div>
                  </div>

                  <div className="chat-content">
                    <p>Across 12 vault sources and 8 recent r/LocalLLaMA threads, here's the shape of the disagreement:</p>
                    <p><b>Your vault</b> leans on Karpathy's framing — RLHF is harder than it looks but a necessary step after SFT. Huyen agrees, and adds that DPO is often "good enough."</p>
                    <p><b>r/LocalLLaMA this week</b> is more skeptical. Two threads argue that for small local models, RLHF is actively harmful — they recommend pure SFT on curated data and calling it done.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="chat-input-wrap">
              <div className="chat-input-box">
                <textarea rows={2} placeholder="Ask Merlin — tools will be called automatically…"/>
                <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>agentic · 5 tools enabled</span>
                  </div>
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
                    <button className="btn ghost" style={{ fontSize: 11.5 }}>/ command</button>
                    <button className="btn primary" style={{ padding: '4px 10px' }}><I.arrowUp style={{width:12,height:12}}/></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .chat-layout-ag {
          flex: 1; min-height: 0;
          display: grid;
          grid-template-columns: 260px 1fr;
          overflow: hidden;
        }
        .chat-tool-rail {
          padding: 22px 18px;
          border-right: 1px solid var(--border);
          overflow-y: auto;
          background: var(--bg-1);
        }
        .tool-section { margin-bottom: 22px; }
        .tool-head {
          font-size: 11px; font-weight: 600;
          margin-bottom: 6px;
          color: var(--text-muted);
          display: flex; justify-content: space-between;
          align-items: baseline;
        }
        .tool-row {
          display: flex; align-items: center; gap: 8px;
          padding: 7px 8px;
          font-size: 12px;
          color: var(--text-subtle);
          border-radius: 5px;
          opacity: 0.5;
        }
        .tool-row.enabled { opacity: 1; }
        .tool-dot {
          width: 5px; height: 5px; border-radius: 50%;
          background: var(--text-faint);
          flex-shrink: 0;
        }
        .tool-row.enabled .tool-dot { background: var(--good); box-shadow: 0 0 6px var(--good); }
        .tool-name {
          font-family: var(--font-mono);
          font-size: 11.5px;
          color: var(--text);
        }
        .tool-desc {
          font-size: 10.5px;
          color: var(--text-subtle);
        }
        .toggle {
          width: 22px; height: 13px;
          border-radius: 10px;
          background: var(--bg-3);
          border: 1px solid var(--border-strong);
          position: relative;
          cursor: pointer;
        }
        .toggle > span {
          position: absolute; left: 1px; top: 1px;
          width: 9px; height: 9px; border-radius: 50%;
          background: var(--text-muted);
          transition: left var(--dur);
        }
        .toggle.on { background: var(--accent-soft); border-color: var(--border-accent); }
        .toggle.on > span { left: 10px; background: var(--accent); }

        .tool-trace {
          display: flex; flex-direction: column; gap: 4px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 10px 12px;
          margin: 8px 0 16px;
        }
        .trace-step {
          display: flex; align-items: center; gap: 10px;
          padding: 4px 0;
          font-size: 11.5px;
          color: var(--text-muted);
        }
        .trace-step.done { color: var(--good); }
        .trace-step.running { color: var(--accent); }
        .trace-args {
          font-size: 10.5px;
          color: var(--text-subtle);
        }
        .spinner {
          width: 11px; height: 11px;
          border: 1.5px solid var(--accent);
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 0.9s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

window.RedditScreen = RedditScreen;
window.AgenticChatScreen = AgenticChatScreen;
