/* global React, I, Sidebar, Topbar, SourcePill, ALL_SOURCES, TAGS, VIDEOS, BLOGS, REDDITS */
const { useState: useStateLib } = React;

function LibraryScreen() {
  const [view, setView] = useStateLib('grid');
  const [activeTag, setActiveTag] = useStateLib(null);
  const [typeFilter, setTypeFilter] = useStateLib('all');

  const filtered = ALL_SOURCES.filter(s => {
    if (typeFilter !== 'all' && s.type !== typeFilter) return false;
    if (activeTag && !s.tags.includes(activeTag)) return false;
    return true;
  });

  return (
    <div className="artboard-root">
      <Sidebar active="library" />
      <div className="main">
        <Topbar crumbs={['Library']} />
        <div className="page">
          <div className="page-wide">
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 24 }}>
              <div>
                <h1 className="page-title">Library</h1>
                <p className="page-subtitle">
                  <span className="mono">{filtered.length}</span> of <span className="mono">{ALL_SOURCES.length}</span> sources{activeTag && <> · filtered by <span className="tag accent"><span className="dot"/>{activeTag}</span></>}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div className="input" style={{ display: 'flex', alignItems: 'center', gap: 8, width: 260, padding: '8px 12px' }}>
                  <I.search style={{ width: 14, height: 14, color: 'var(--text-subtle)' }} />
                  <input placeholder="Search library…" style={{ background: 'transparent', border: 0, outline: 0, color: 'var(--text)', flex: 1, fontSize: 13 }} />
                  <span className="kbd">/</span>
                </div>
                <div className="view-toggle">
                  <button className={view==='grid'?'active':''} onClick={()=>setView('grid')}><I.grid style={{width:13,height:13}}/></button>
                  <button className={view==='list'?'active':''} onClick={()=>setView('list')}><I.list style={{width:13,height:13}}/></button>
                </div>
              </div>
            </div>

            {/* Filter chips */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
              {[
                { id: 'all', label: 'Everything', count: ALL_SOURCES.length },
                { id: 'youtube', label: 'YouTube', count: VIDEOS.length },
                { id: 'blog', label: 'Blogs', count: BLOGS.length },
                { id: 'reddit', label: 'Reddit', count: REDDITS.length },
              ].map(f => (
                <button key={f.id} className={"filter-chip" + (typeFilter===f.id?' is-active':'')} onClick={()=>setTypeFilter(f.id)}>
                  {f.label} <span className="mono" style={{ fontSize: 10.5, opacity: 0.6 }}>{f.count}</span>
                </button>
              ))}
              <div style={{ width: 1, background: 'var(--border)', margin: '0 4px' }} />
              {TAGS.slice(0,5).map(t => (
                <button key={t.name} className={"filter-chip" + (activeTag===t.name?' is-active':'')} onClick={()=>setActiveTag(activeTag===t.name?null:t.name)}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color, display: 'inline-block' }} />
                  {t.name}
                </button>
              ))}
            </div>

            {/* Grid */}
            {view === 'grid' && (
              <div className="lib-grid">
                {filtered.map(s => (
                  <div key={s.id} className="lib-card">
                    <div className="lib-thumb">
                      {s.type === 'youtube' && <>
                        <div className="img-ph" style={{ width: '100%', height: '100%' }}>thumbnail</div>
                        <div className="lib-duration">{s.duration}</div>
                        <div className="lib-play"><I.yt /></div>
                      </>}
                      {s.type === 'blog' && (
                        <div style={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', background: 'var(--bg-2)', color: 'var(--text-subtle)' }}>
                          <I.paper style={{ width: 28, height: 28 }} />
                        </div>
                      )}
                      {s.type === 'reddit' && (
                        <div style={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', background: 'var(--bg-2)', color: 'var(--text-subtle)' }}>
                          <I.reddit style={{ width: 28, height: 28 }} />
                        </div>
                      )}
                    </div>
                    <div className="lib-body">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <SourcePill type={s.type} />
                        <span className="text-subtle mono" style={{ fontSize: 10.5 }}>{s.added}</span>
                      </div>
                      <div className="lib-title">{s.title}</div>
                      <div className="lib-meta">{s.channel || s.author || s.subreddit}</div>
                      <div className="lib-summary">{s.summary}</div>
                      <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                        {s.tags.map(t => <span key={t} className="tag"><span className="dot" style={{ background: TAGS.find(x=>x.name===t)?.color || '#999'}}/>{t}</span>)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {view === 'list' && (
              <div className="lib-list">
                {filtered.map(s => (
                  <div key={s.id} className="lib-list-row">
                    <SourcePill type={s.type} />
                    <span style={{ flex: 1, fontWeight: 500, fontSize: 13.5 }}>{s.title}</span>
                    <span className="text-subtle" style={{ fontSize: 12 }}>{s.channel || s.author || s.subreddit}</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {s.tags.map(t => <span key={t} className="tag" style={{ fontSize: 10 }}><span className="dot" style={{ background: TAGS.find(x=>x.name===t)?.color || '#999'}}/>{t}</span>)}
                    </div>
                    <span className="text-subtle mono" style={{ fontSize: 10.5, width: 60, textAlign: 'right' }}>{s.added}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .view-toggle {
          display: flex; background: var(--bg-1);
          border: 1px solid var(--border); border-radius: 7px;
          padding: 2px;
        }
        .view-toggle button {
          background: transparent; border: 0;
          padding: 5px 10px;
          border-radius: 5px;
          color: var(--text-muted);
          cursor: pointer;
        }
        .view-toggle button.active {
          background: var(--bg-3);
          color: var(--text);
        }

        .filter-chip {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 5px 10px;
          background: transparent;
          border: 1px solid var(--border);
          border-radius: 20px;
          color: var(--text-muted);
          font-size: 12px;
          cursor: pointer;
          font-family: inherit;
          transition: all var(--dur);
        }
        .filter-chip:hover { color: var(--text); border-color: var(--border-strong); }
        .filter-chip.is-active {
          background: var(--accent-soft);
          border-color: var(--border-accent);
          color: var(--accent);
        }

        .lib-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 18px;
          margin-top: 24px;
        }
        .lib-card {
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          transition: all var(--dur);
          cursor: pointer;
        }
        .lib-card:hover {
          border-color: var(--border-strong);
          transform: translateY(-1px);
        }
        .lib-thumb {
          position: relative;
          aspect-ratio: 16/9;
          background: var(--bg-2);
          overflow: hidden;
        }
        .lib-duration {
          position: absolute; bottom: 8px; right: 8px;
          background: rgba(0,0,0,0.7); color: #fff;
          padding: 2px 6px; border-radius: 4px;
          font-family: var(--font-mono); font-size: 10.5px;
        }
        .lib-play {
          position: absolute; top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          width: 40px; height: 40px; border-radius: 50%;
          background: rgba(0,0,0,0.5);
          display: grid; place-items: center;
          color: #fff;
          opacity: 0; transition: opacity var(--dur);
        }
        .lib-card:hover .lib-play { opacity: 1; }

        .lib-body { padding: 14px; }
        .lib-title {
          font-size: 14px; font-weight: 600;
          line-height: 1.3;
          letter-spacing: -0.005em;
          margin-bottom: 4px;
          display: -webkit-box;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 2;
          overflow: hidden;
        }
        .lib-meta {
          font-size: 11.5px; color: var(--text-muted);
          margin-bottom: 8px;
        }
        .lib-summary {
          font-size: 12px;
          color: var(--text-muted);
          line-height: 1.45;
          display: -webkit-box;
          -webkit-box-orient: vertical;
          -webkit-line-clamp: 3;
          overflow: hidden;
        }

        .lib-list {
          margin-top: 24px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
        }
        .lib-list-row {
          display: flex; align-items: center; gap: 14px;
          padding: 12px 16px;
          border-bottom: 1px solid var(--border);
          cursor: pointer;
          transition: background var(--dur);
        }
        .lib-list-row:last-child { border-bottom: 0; }
        .lib-list-row:hover { background: var(--bg-1); }
      `}</style>
    </div>
  );
}

window.LibraryScreen = LibraryScreen;
