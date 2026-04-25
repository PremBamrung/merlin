/* global React, I, Sidebar, Topbar, SourcePill, TAGS */
const { useState: useStateNews } = React;

function DigestScreen() {
  const sections = [
    {
      title: 'From your trusted voices',
      subtitle: '4 new pieces · based on authors you follow',
      items: [
        { type: 'youtube', title: "Let's reproduce GPT-2 (124M)", author: 'Andrej Karpathy', meta: '4h ago · 2:14:18', why: 'You follow Karpathy · tag: llm-research', summary: 'A full four-hour build, from tokenizer to training loop. Continuation of the nanoGPT series. Karpathy calls this the "compressed PhD" version.', match: 0.98 },
        { type: 'blog', title: 'Scaling laws revisited: what Chinchilla missed', author: 'Chip Huyen', meta: '1d ago · 14 min', why: 'You follow Huyen · tag: llm-research', summary: "A critical re-read of the compute-optimal frontier, arguing the community over-indexed on compute and under-indexed on data quality.", match: 0.94 },
        { type: 'youtube', title: 'Rust beyond the borrow checker', author: 'Jon Gjengset', meta: '2d ago · 58:22', why: 'You follow Jon · tag: rust', summary: "Deep dive on Rust's type system past the surface ownership story. Pinning, variance, and why async is still hard.", match: 0.88 },
      ],
    },
    {
      title: 'Recommended from YouTube',
      subtitle: '6 picks from your subscriptions and watch-adjacent · matched to your tags',
      items: [
        { type: 'youtube', title: 'The hidden cost of vector databases in production', author: 'LLMOps.io', meta: '3h ago · 22:04', why: 'Matches your tag: mlops · 3 similar sources in vault', summary: "Benchmarks of Pinecone, Weaviate, Qdrant under realistic load. Spoiler: the cost surprise is re-indexing, not queries.", match: 0.91 },
        { type: 'youtube', title: 'Why Obsidian is losing to plain markdown + git', author: 'No Boilerplate', meta: '1d ago · 14:08', why: 'Matches your tag: pkm · 6 similar sources', summary: "A manifesto for stripping PKM back to files on disk, version-controlled. Argues every abstraction above markdown fights you eventually.", match: 0.87 },
      ],
    },
    {
      title: 'From authors you might like',
      subtitle: '2 suggested voices · based on your library',
      items: [
        { type: 'blog', title: 'The Bitter Lesson, 10 years on', author: 'Sara Hooker', meta: 'new voice', why: "93% of your llm-research sources cite adjacent ideas", summary: "Hooker's retrospective on scaling dogma. Her throughline: we mistake 'method-of-the-month' for progress.", match: 0.82, isNew: true },
      ],
    },
  ];

  return (
    <div className="artboard-root">
      <Sidebar active="digest" />
      <div className="main">
        <Topbar crumbs={['Digest', 'Wednesday morning']}
          actions={<>
            <button className="btn ghost"><I.settings/> Sources</button>
            <button className="btn ghost"><I.share/> Send to email</button>
          </>}/>
        <div className="page">
          <div className="page-narrow">
            <div style={{ marginBottom: 28 }}>
              <div className="mono" style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-subtle)', marginBottom: 6 }}>Wednesday morning · April 22</div>
              <h1 className="page-title">Your digest <span className="dim">— 12 new things, curated.</span></h1>
              <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '6px 0 0' }}>
                Pulled from your trusted authors + YouTube subs, filtered against your tags. <span className="text-accent" style={{ cursor: 'pointer' }}>Adjust what gets in →</span>
              </p>
            </div>

            <div className="digest-stats">
              <div><div className="mono-k">12</div><div className="mono-l">picked</div></div>
              <div className="stat-sep"/>
              <div><div className="mono-k">47</div><div className="mono-l">scanned</div></div>
              <div className="stat-sep"/>
              <div><div className="mono-k">8</div><div className="mono-l">voices</div></div>
              <div className="stat-sep"/>
              <div><div className="mono-k">6</div><div className="mono-l">tags matched</div></div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                <button className="chip-sm active">Today</button>
                <button className="chip-sm">Week</button>
                <button className="chip-sm">Archive</button>
              </div>
            </div>

            {sections.map(sec => (
              <div key={sec.title} style={{ marginTop: 28 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 22, margin: 0, fontWeight: 400 }}>{sec.title}</h2>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{sec.subtitle}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {sec.items.map((it, i) => (
                    <div key={i} className="digest-card">
                      <div className="digest-thumb">
                        {it.type === 'youtube' && <I.yt style={{ width: 22, height: 22 }} />}
                        {it.type === 'blog' && <I.paper style={{ width: 22, height: 22 }} />}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                          <SourcePill type={it.type} />
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{it.author}</span>
                          <span className="text-subtle mono" style={{ fontSize: 10.5 }}>· {it.meta}</span>
                          {it.isNew && <span className="tag accent" style={{ marginLeft: 'auto', fontSize: 10 }}><span className="dot"/>new voice</span>}
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 5, lineHeight: 1.3 }}>{it.title}</div>
                        <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 8 }}>{it.summary}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{it.why}</span>
                          <span className="match-bar"><span style={{ width: `${it.match*100}%` }}/></span>
                          <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>{Math.round(it.match*100)}%</span>
                          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                            <button className="btn ghost" style={{ fontSize: 11, padding: '3px 8px' }}>Ingest</button>
                            <button className="btn ghost" style={{ fontSize: 11, padding: '3px 8px' }}>Skip</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <style>{`
        .digest-stats {
          display: flex; align-items: center; gap: 20px;
          padding: 14px 18px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 10px;
          margin-bottom: 12px;
        }
        .stat-sep { width: 1px; height: 24px; background: var(--border); }
        .mono-k { font-family: var(--font-display); font-size: 22px; line-height: 1; }
        .mono-l { font-size: 10.5px; color: var(--text-subtle); margin-top: 3px; text-transform: uppercase; letter-spacing: 0.1em; }
        .chip-sm {
          background: transparent; border: 1px solid var(--border);
          padding: 4px 10px; border-radius: 14px;
          color: var(--text-muted); font-size: 11px;
          cursor: pointer; font-family: inherit;
        }
        .chip-sm.active { background: var(--bg-3); color: var(--text); border-color: var(--border-strong); }

        .digest-card {
          display: flex; gap: 14px;
          padding: 14px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 10px;
          transition: border-color var(--dur);
          cursor: pointer;
        }
        .digest-card:hover { border-color: var(--border-accent); }
        .digest-thumb {
          width: 48px; height: 48px;
          border-radius: 8px;
          background: var(--bg-2);
          display: grid; place-items: center;
          color: var(--text-muted);
          flex-shrink: 0;
        }
        .match-bar {
          width: 50px; height: 3px;
          background: var(--bg-3); border-radius: 2px;
          display: inline-block;
          overflow: hidden;
        }
        .match-bar > span {
          display: block; height: 100%; background: var(--accent);
        }
      `}</style>
    </div>
  );
}

// Sources-to-follow surface — manage trusted voices + feeds
function FollowsScreen() {
  const voices = [
    { who: 'Andrej Karpathy', platforms: ['youtube', 'blog'], tag: 'llm-research', last: 'posted 4h ago', active: true },
    { who: 'Chip Huyen', platforms: ['blog'], tag: 'llm-research', last: '1d ago', active: true },
    { who: 'Jon Gjengset', platforms: ['youtube'], tag: 'rust', last: '2d ago', active: true },
    { who: 'No Boilerplate', platforms: ['youtube'], tag: 'rust · pkm', last: '3d ago', active: true },
    { who: 'Oliver Reichenstein', platforms: ['blog'], tag: 'design-systems', last: '1w ago', active: true },
    { who: 'Simon Willison', platforms: ['blog'], tag: 'llm-research · tools', last: '6h ago', active: false },
  ];
  const subs = [
    { name: 'r/LocalLLaMA', type: 'reddit', rule: 'top · weekly', tag: 'llm-research', count: 8 },
    { name: 'r/rust', type: 'reddit', rule: 'top · weekly', tag: 'rust', count: 4 },
    { name: 'YouTube subscriptions', type: 'youtube', rule: 'new uploads matching tags', tag: 'all tags', count: 23 },
    { name: 'Hacker News', type: 'web', rule: 'front page · score > 300', tag: 'auto-detected', count: 11 },
  ];

  return (
    <div className="artboard-root">
      <Sidebar active="follows" />
      <div className="main">
        <Topbar crumbs={['Sources to follow']}
          actions={<><button className="btn primary"><I.plus/> Add voice</button></>}/>
        <div className="page">
          <div className="page-narrow">
            <h1 className="page-title">Voices & feeds</h1>
            <p className="page-subtitle">Who Merlin scans for your digest. Add people you trust — Merlin pulls their new work, matches it against your tags, and only surfaces what's worth your time.</p>

            <div style={{ marginTop: 24 }}>
              <div className="follow-head">
                <span className="follow-title">Authors you follow <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>{voices.length}</span></span>
                <button className="btn ghost" style={{ fontSize: 11 }}>Import from OPML</button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                {voices.map(v => (
                  <div key={v.who} className="voice-row">
                    <div className="voice-avatar">{v.who[0]}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{v.who}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{v.tag}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {v.platforms.includes('youtube') && <span className="src-bubble yt"><I.yt style={{width:10,height:10}}/></span>}
                      {v.platforms.includes('blog') && <span className="src-bubble blog"><I.paper style={{width:10,height:10}}/></span>}
                    </div>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', width: 100, textAlign: 'right' }}>{v.last}</span>
                    <div className={"toggle" + (v.active ? ' on' : '')}><span/></div>
                  </div>
                ))}
                <button className="voice-add">+ add a trusted voice · Karpathy, Huyen, anyone…</button>
              </div>
            </div>

            <div style={{ marginTop: 32 }}>
              <div className="follow-head">
                <span className="follow-title">Feeds & subscriptions <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>{subs.length}</span></span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                {subs.map(s => (
                  <div key={s.name} className="voice-row">
                    <SourcePill type={s.type}/>
                    <div style={{ flex: 1, minWidth: 0, marginLeft: 8 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500 }}>{s.name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-subtle)' }}>{s.rule}</div>
                    </div>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>{s.count}/week</span>
                    <div className="toggle on"><span/></div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: 32 }}>
              <div className="follow-head">
                <span className="follow-title">Digest schedule</span>
              </div>
              <div style={{ padding: 16, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10, marginTop: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <I.clock style={{ width: 16, height: 16, color: 'var(--accent)' }}/>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>Daily at 7:00am</div>
                    <div style={{ fontSize: 11, color: 'var(--text-subtle)' }}>You'll see fresh matches waiting when you open Merlin</div>
                  </div>
                  <button className="btn ghost" style={{ fontSize: 11 }}>Change</button>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 14 }}>
                  <label className="opt-check"><span className="checkbox checked"><I.check style={{width:9,height:9}}/></span> Show in Merlin</label>
                  <label className="opt-check"><span className="checkbox"/> Email to me</label>
                  <label className="opt-check"><span className="checkbox"/> Push to RSS</label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <style>{`
        .follow-head { display: flex; align-items: center; }
        .follow-title {
          flex: 1;
          font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
          color: var(--text-muted); font-weight: 600;
        }
        .voice-row {
          display: flex; align-items: center; gap: 12px;
          padding: 10px 14px;
          background: var(--bg-1); border: 1px solid var(--border);
          border-radius: 8px;
        }
        .voice-avatar {
          width: 30px; height: 30px; border-radius: 50%;
          background: var(--accent-soft); color: var(--accent);
          display: grid; place-items: center;
          font-family: var(--font-display);
          font-size: 16px;
        }
        .src-bubble {
          width: 22px; height: 22px; border-radius: 5px;
          background: var(--bg-2);
          display: grid; place-items: center;
        }
        .src-bubble.yt { color: #e0826a; }
        .src-bubble.blog { color: #8db089; }
        .voice-add {
          border: 1px dashed var(--border-strong);
          background: transparent; padding: 10px;
          border-radius: 8px; color: var(--text-subtle);
          font-size: 12px; cursor: pointer; font-family: inherit;
        }
        .voice-add:hover { border-color: var(--accent); color: var(--accent); }
        .opt-check { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); cursor: pointer; padding: 4px 10px; }
      `}</style>
    </div>
  );
}

// Mobile — single-column responsive shell
function MobileScreen() {
  const [tab, setTab] = useStateNews('today');
  return (
    <div style={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', background: 'var(--bg)', padding: 24 }}>
      <div className="phone-frame">
        <div className="phone-notch"/>
        <div className="phone-screen" data-theme="obsidian">
          <div className="mob-top">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 22, color: 'var(--accent)', fontStyle: 'italic' }}>✦</span>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 22 }}>Merlin</span>
            </div>
            <I.search style={{ width: 18, height: 18, color: 'var(--text-muted)' }}/>
          </div>

          {tab === 'today' && <>
            <div style={{ padding: '14px 16px 0' }}>
              <div className="mono" style={{ fontSize: 10, color: 'var(--text-subtle)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>Wed · 7:02am</div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 28, margin: 0, lineHeight: 1.1, fontWeight: 400 }}>Good morning.</h2>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>12 new picks waiting.</p>
            </div>

            <div className="mob-omnibox">
              <I.sparkle style={{ width: 14, height: 14, color: 'var(--accent)' }}/>
              <span style={{ fontSize: 13, color: 'var(--text-subtle)' }}>Paste a link or ask…</span>
              <I.arrowUp style={{ width: 14, height: 14, color: 'var(--text-subtle)', marginLeft: 'auto' }}/>
            </div>

            <div style={{ padding: '0 16px', marginTop: 20 }}>
              <div className="mob-sec-head">Today's digest</div>
              {[
                { type: 'youtube', title: "Let's reproduce GPT-2 (124M)", author: 'Karpathy · 2:14', match: 0.98 },
                { type: 'blog', title: 'Scaling laws revisited', author: 'Huyen · 14min', match: 0.94 },
                { type: 'youtube', title: 'Vector DB hidden costs', author: 'LLMOps.io · 22min', match: 0.91 },
              ].map((it, i) => (
                <div key={i} className="mob-card">
                  <div className="mob-thumb">
                    {it.type === 'youtube' && <I.yt style={{width:16,height:16,color:'#e0826a'}}/>}
                    {it.type === 'blog' && <I.paper style={{width:16,height:16,color:'#8db089'}}/>}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3 }}>{it.title}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginTop: 3 }}>{it.author}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--accent)' }}>{Math.round(it.match*100)}%</span>
                </div>
              ))}
            </div>
          </>}

          {tab === 'library' && <>
            <div style={{ padding: '14px 16px' }}>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 26, margin: '0 0 10px', fontWeight: 400 }}>Library</h2>
              <div style={{ display: 'flex', gap: 5, overflowX: 'auto', marginBottom: 12 }}>
                {['All · 248', 'llm-research · 34', 'rust · 22', 'design-systems · 18'].map(t => (
                  <span key={t} className="mob-chip">{t}</span>
                ))}
              </div>
              {[1,2,3,4].map(i => (
                <div key={i} className="mob-card">
                  <div className="mob-thumb"><I.yt style={{width:16,height:16,color:'#e0826a'}}/></div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>Saved video {i}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>channel · 2d</div>
                  </div>
                </div>
              ))}
            </div>
          </>}

          {tab === 'chat' && <>
            <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', height: 'calc(100% - 120px)' }}>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 26, margin: '0 0 10px', fontWeight: 400 }}>Chat</h2>
              <div style={{ flex: 1, overflowY: 'auto', fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                <div style={{ marginBottom: 12 }}><b style={{ color: 'var(--text)' }}>you</b> — What did Karpathy say about RLHF?</div>
                <div><b style={{ color: 'var(--accent)' }}>✦ Merlin</b> — At 17:30, he frames RLHF as optimizing a noisy proxy…</div>
              </div>
              <div className="mob-omnibox" style={{ marginTop: 12 }}>
                <span style={{ fontSize: 12.5, color: 'var(--text-subtle)', flex: 1 }}>Ask your library…</span>
                <I.arrowUp style={{ width: 14, height: 14, color: 'var(--accent)' }}/>
              </div>
            </div>
          </>}

          {/* Bottom tabs */}
          <div className="mob-tabs">
            {[
              { id: 'today', label: 'Today', Icon: I.sparkle },
              { id: 'library', label: 'Library', Icon: I.library },
              { id: 'chat', label: 'Chat', Icon: I.chat },
              { id: 'more', label: 'More', Icon: I.grid },
            ].map(t => {
              const Icon = t.Icon;
              return (
                <div key={t.id} className={"mob-tab" + (tab === t.id ? ' active' : '')} onClick={() => setTab(t.id)}>
                  <Icon style={{ width: 18, height: 18 }}/>
                  <span>{t.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <style>{`
        .phone-frame {
          width: 360px; height: 740px;
          background: #2a2826;
          border-radius: 44px;
          padding: 10px;
          box-shadow: 0 30px 80px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(255,255,255,0.04);
          position: relative;
        }
        .phone-notch {
          position: absolute;
          top: 18px; left: 50%; transform: translateX(-50%);
          width: 110px; height: 28px;
          background: #000;
          border-radius: 20px;
          z-index: 2;
        }
        .phone-screen {
          width: 100%; height: 100%;
          background: var(--bg);
          border-radius: 34px;
          overflow: hidden;
          position: relative;
        }
        .mob-top {
          display: flex; align-items: center; justify-content: space-between;
          padding: 54px 20px 10px;
        }
        .mob-omnibox {
          margin: 16px 16px 0;
          display: flex; align-items: center; gap: 10px;
          padding: 12px 14px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 12px;
        }
        .mob-sec-head {
          font-size: 10.5px; letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--text-muted);
          margin-bottom: 10px;
          font-weight: 600;
        }
        .mob-card {
          display: flex; align-items: center; gap: 10px;
          padding: 10px;
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 10px;
          margin-bottom: 6px;
        }
        .mob-thumb {
          width: 32px; height: 32px; border-radius: 6px;
          background: var(--bg-2);
          display: grid; place-items: center;
          flex-shrink: 0;
        }
        .mob-chip {
          padding: 4px 10px;
          font-size: 11px;
          background: var(--bg-1); border: 1px solid var(--border);
          border-radius: 20px; white-space: nowrap;
          color: var(--text-muted);
        }
        .mob-tabs {
          position: absolute; bottom: 0; left: 0; right: 0;
          display: grid; grid-template-columns: repeat(4, 1fr);
          background: var(--bg-1);
          border-top: 1px solid var(--border);
          padding: 8px 0 22px;
        }
        .mob-tab {
          display: flex; flex-direction: column; align-items: center; gap: 3px;
          color: var(--text-subtle);
          font-size: 10px;
          cursor: pointer;
        }
        .mob-tab.active { color: var(--accent); }
      `}</style>
    </div>
  );
}

// Storage / settings — shows md + db architecture
function StorageScreen() {
  return (
    <div className="artboard-root">
      <Sidebar active="settings"/>
      <div className="main">
        <Topbar crumbs={['Settings', 'Storage']}/>
        <div className="page">
          <div className="page-narrow">
            <h1 className="page-title">Storage</h1>
            <p className="page-subtitle">Your knowledge stays local. Markdown for docs, a database for search and graph relationships. Self-hostable.</p>

            <div className="storage-diagram">
              <div className="st-col">
                <div className="st-col-head"><I.paper style={{width:14,height:14}}/> Documents</div>
                <div className="st-card">
                  <div className="mono" style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 6 }}>~/merlin/vault/</div>
                  <div className="fs-tree">
                    <div>├── youtube/</div>
                    <div style={{ paddingLeft: 20 }}>│   ├── karpathy-state-of-gpt.md</div>
                    <div style={{ paddingLeft: 20 }}>│   ├── nanogpt-scratch.md</div>
                    <div>├── blogs/</div>
                    <div style={{ paddingLeft: 20 }}>│   ├── huyen-llm-production.md</div>
                    <div>├── reddit/</div>
                    <div style={{ paddingLeft: 20 }}>│   └── pkm-setups-2026.md</div>
                    <div>└── assets/</div>
                  </div>
                </div>
                <div className="st-note">One markdown file per source. Human-readable, grep-able, git-able.</div>
              </div>

              <div className="st-arrow">→ indexed by →</div>

              <div className="st-col">
                <div className="st-col-head"><I.library style={{width:14,height:14}}/> Database</div>
                <div className="st-card">
                  <div className="db-toggle">
                    <button className="active">SQLite</button>
                    <button>Postgres</button>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)', marginTop: 12, marginBottom: 6 }}>tables</div>
                  <div className="fs-tree">
                    <div>• sources <span className="text-subtle">— id, type, url, path</span></div>
                    <div>• summaries <span className="text-subtle">— source_id, text, length</span></div>
                    <div>• tags <span className="text-subtle">— name, color</span></div>
                    <div>• source_tags <span className="text-subtle">— many-to-many</span></div>
                    <div>• embeddings <span className="text-subtle">— vector(1536)</span></div>
                    <div>• messages <span className="text-subtle">— chat history</span></div>
                  </div>
                </div>
                <div className="st-note">Handles search, graph edges, embeddings, and chat history. Swap SQLite for Postgres with one env var.</div>
              </div>
            </div>

            <div style={{ marginTop: 28 }}>
              <div className="follow-head" style={{ marginBottom: 12 }}>
                <span className="follow-title">Backend</span>
              </div>
              <div style={{ padding: 16, background: 'var(--bg-1)', border: '1px solid var(--border)', borderRadius: 10 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
                  <div>
                    <div className="meta-k">API</div>
                    <div className="meta-v mono">FastAPI · :8000</div>
                  </div>
                  <div>
                    <div className="meta-k">DB</div>
                    <div className="meta-v mono">SQLite · merlin.db</div>
                  </div>
                  <div>
                    <div className="meta-k">Frontend</div>
                    <div className="meta-v mono">served at /</div>
                  </div>
                </div>
                <div style={{ marginTop: 14, padding: 12, background: 'var(--bg-2)', borderRadius: 6, fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--text-muted)' }}>
                  $ docker compose up<br/>
                  <span style={{ color: 'var(--good)' }}>✓</span> merlin running at http://localhost:8000
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <style>{`
        .storage-diagram {
          display: grid;
          grid-template-columns: 1fr auto 1fr;
          gap: 20px;
          align-items: start;
          margin-top: 20px;
        }
        .st-col-head {
          display: flex; align-items: center; gap: 8px;
          font-size: 11px; text-transform: uppercase;
          letter-spacing: 0.12em;
          color: var(--text-muted); font-weight: 600;
          margin-bottom: 10px;
        }
        .st-card {
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 14px;
        }
        .st-note {
          font-size: 11.5px; color: var(--text-subtle);
          margin-top: 8px; line-height: 1.5;
        }
        .fs-tree {
          font-family: var(--font-mono);
          font-size: 11.5px;
          line-height: 1.8;
          color: var(--text-muted);
        }
        .st-arrow {
          font-family: var(--font-mono);
          font-size: 11px;
          color: var(--text-subtle);
          text-transform: uppercase;
          letter-spacing: 0.1em;
          padding: 40px 8px 0;
          text-align: center;
          width: 140px;
        }
        .db-toggle {
          display: flex; background: var(--bg-2);
          border: 1px solid var(--border);
          border-radius: 6px; padding: 2px;
          width: fit-content;
        }
        .db-toggle button {
          background: transparent; border: 0;
          padding: 4px 12px;
          font-family: var(--font-mono);
          font-size: 11px;
          color: var(--text-muted);
          cursor: pointer;
          border-radius: 4px;
        }
        .db-toggle button.active {
          background: var(--bg-3);
          color: var(--text);
        }
      `}</style>
    </div>
  );
}

window.DigestScreen = DigestScreen;
window.FollowsScreen = FollowsScreen;
window.MobileScreen = MobileScreen;
window.StorageScreen = StorageScreen;
