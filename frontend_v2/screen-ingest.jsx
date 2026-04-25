/* global React, I, Sidebar, Topbar, SourcePill, TAGS */
const { useState: useStateIngest } = React;

function IngestReviewScreen() {
  const [selected, setSelected] = useStateIngest(new Set(['llm-research', 'rlhf', 'karpathy']));
  const toggle = (t) => {
    const next = new Set(selected);
    next.has(t) ? next.delete(t) : next.add(t);
    setSelected(next);
  };

  // Auto-proposed tags — mix of existing + new suggestions
  const proposed = [
    { name: 'llm-research', existing: true, count: 34, color: '#c9a9ff', conf: 0.94 },
    { name: 'fundamentals', existing: true, count: 15, color: '#9ec9b8', conf: 0.87 },
    { name: 'rlhf', existing: false, conf: 0.82, reason: 'new — you don\'t have a tag for this yet' },
    { name: 'karpathy', existing: false, conf: 0.78, reason: 'author/speaker tag' },
    { name: 'pytorch', existing: true, count: 12, color: '#b8a0ff', conf: 0.41, weak: true },
  ];

  const related = [
    { name: 'system-design', count: 6, color: '#a8c4e8' },
    { name: 'alignment', count: 4, color: '#e8c47c' },
  ];

  return (
    <div className="artboard-root">
      <Sidebar active="inbox" />
      <div className="main">
        <Topbar crumbs={['Inbox', 'Review ingestion']}
          actions={<><button className="btn ghost">Skip</button><button className="btn primary"><I.check/> Save to Library</button></>}/>
        <div className="page">
          <div style={{ maxWidth: 780, margin: '0 auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <SourcePill type="youtube"/>
              <span className="mono" style={{ fontSize: 11, color: 'var(--text-subtle)' }}>ingested 2 minutes ago</span>
              <span className="tag accent" style={{ marginLeft: 'auto' }}><span className="dot"/>ready to review</span>
            </div>
            <h1 className="page-title" style={{ fontSize: 30 }}>Andrej Karpathy: The State of GPT</h1>
            <p className="page-subtitle">Merlin has summarized this source and proposed tags + metadata. Adjust anything before saving to your Library.</p>

            {/* Summary preview */}
            <div className="review-block">
              <div className="review-block-head">
                <span>Summary</span>
                <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
                  <button className="mini-btn">short</button>
                  <button className="mini-btn active">medium</button>
                  <button className="mini-btn">long</button>
                </div>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--text-muted)', margin: 0 }}>
                A pragmatic tour of the full LLM training pipeline — from pretraining and instruction tuning to RLHF, plus when to use which model. Karpathy emphasizes treating LLMs as "System 1" thinkers: fast, intuitive, and prone to mistakes when asked to reason in one shot.
              </p>
              <button className="regen-btn"><I.sparkle style={{width:11,height:11}}/> Regenerate</button>
            </div>

            {/* Tag proposal */}
            <div className="review-block">
              <div className="review-block-head">
                <span>Tags <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 6 }}>·  Merlin proposed 5</span></span>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 'auto' }}>{selected.size} selected</span>
              </div>

              <div style={{ fontSize: 11.5, color: 'var(--text-subtle)', marginBottom: 10 }}>
                Existing tags are preferred. If a new tag fits better, Merlin will propose one — you decide.
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {proposed.map(p => (
                  <div key={p.name} className={"propose-row" + (selected.has(p.name) ? ' selected' : '') + (p.weak ? ' weak' : '')} onClick={() => toggle(p.name)}>
                    <span className={"propose-check" + (selected.has(p.name) ? ' checked' : '')}>
                      {selected.has(p.name) && <I.check style={{width:10,height:10}}/>}
                    </span>
                    <span className="swatch" style={{ background: p.color || 'var(--text-faint)' }} />
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</span>
                    {p.existing ? (
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)' }}>existing · {p.count} sources</span>
                    ) : (
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--accent)' }}>proposed · new</span>
                    )}
                    {p.reason && <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', marginLeft: 8 }}>{p.reason}</span>}
                    <span className="mono conf-bar" style={{ marginLeft: 'auto' }}>
                      <span style={{ width: `${p.conf * 100}%` }} />
                    </span>
                    <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', minWidth: 34, textAlign: 'right' }}>{Math.round(p.conf*100)}%</span>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Related in your vault</span>
                {related.map(r => (
                  <span key={r.name} className="tag" style={{ cursor: 'pointer' }}>
                    <span className="dot" style={{ background: r.color }}/>
                    {r.name}
                    <span className="mono" style={{ fontSize: 9.5, color: 'var(--text-subtle)', marginLeft: 2 }}>{r.count}</span>
                  </span>
                ))}
                <span className="tag" style={{ borderStyle: 'dashed', cursor: 'pointer' }}>+ custom tag</span>
              </div>
            </div>

            {/* Metadata */}
            <div className="review-block">
              <div className="review-block-head"><span>Metadata</span></div>
              <div className="meta-grid">
                <div><div className="meta-k">Source type</div><div className="meta-v">YouTube video</div></div>
                <div><div className="meta-k">Duration</div><div className="meta-v mono">42:12</div></div>
                <div><div className="meta-k">Channel</div><div className="meta-v">Microsoft Build</div></div>
                <div><div className="meta-k">Speaker</div><div className="meta-v">Andrej Karpathy</div></div>
                <div><div className="meta-k">Published</div><div className="meta-v mono">2023-05-24</div></div>
                <div><div className="meta-k">Language</div><div className="meta-v">English</div></div>
                <div><div className="meta-k">Views</div><div className="meta-v mono">1.2M</div></div>
                <div><div className="meta-k">Topics extracted</div><div className="meta-v mono">5</div></div>
                <div className="meta-full"><div className="meta-k">URL</div><div className="meta-v mono" style={{ fontSize: 12 }}>youtube.com/watch?v=bZQun8Y4L2A</div></div>
              </div>
            </div>

            {/* Collection placement */}
            <div className="review-block">
              <div className="review-block-head"><span>Collections</span></div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span className="tag accent"><span className="dot"/>LLM research <I.check style={{width:10,height:10,marginLeft:2}}/></span>
                <span className="tag" style={{ cursor: 'pointer' }}><I.plus style={{width:10,height:10}}/> Pinned for later</span>
                <span className="tag" style={{ cursor: 'pointer' }}><I.plus style={{width:10,height:10}}/> Reference material</span>
                <span className="tag" style={{ borderStyle: 'dashed', cursor: 'pointer' }}>+ new collection</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <style>{`
        .review-block {
          background: var(--bg-1);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 18px 20px;
          margin-bottom: 14px;
          position: relative;
        }
        .review-block-head {
          display: flex; align-items: center;
          font-size: 11.5px; letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--text-muted); font-weight: 600;
          margin-bottom: 12px;
        }
        .mini-btn {
          background: transparent; border: 1px solid var(--border);
          border-radius: 4px;
          padding: 2px 8px;
          font-size: 10.5px;
          color: var(--text-muted);
          cursor: pointer;
          font-family: inherit;
          text-transform: none;
          letter-spacing: 0;
        }
        .mini-btn.active { background: var(--bg-3); color: var(--text); border-color: var(--border-strong); }
        .regen-btn {
          position: absolute; top: 14px; right: 18px;
          background: transparent; border: 0;
          color: var(--text-subtle);
          font-size: 10.5px;
          cursor: pointer;
          display: inline-flex; align-items: center; gap: 4px;
          font-family: inherit;
        }
        .regen-btn:hover { color: var(--accent); }

        .propose-row {
          display: flex; align-items: center; gap: 10px;
          padding: 9px 12px;
          border: 1px solid var(--border);
          border-radius: 7px;
          background: var(--bg-2);
          cursor: pointer;
          transition: all var(--dur);
        }
        .propose-row:hover { border-color: var(--border-strong); }
        .propose-row.selected {
          border-color: var(--border-accent);
          background: var(--accent-soft);
        }
        .propose-row.weak { opacity: 0.55; }
        .propose-check {
          width: 14px; height: 14px;
          border: 1px solid var(--border-strong);
          border-radius: 3px;
          display: grid; place-items: center;
          flex-shrink: 0;
          color: var(--bg);
        }
        .propose-check.checked { background: var(--accent); border-color: var(--accent); }
        .propose-row .swatch {
          width: 7px; height: 7px; border-radius: 2px; flex-shrink: 0;
        }
        .conf-bar {
          width: 40px; height: 3px;
          background: var(--bg-3); border-radius: 2px;
          overflow: hidden;
          display: inline-block;
        }
        .conf-bar > span {
          display: block; height: 100%; background: var(--accent);
        }

        .meta-grid {
          display: grid; grid-template-columns: 1fr 1fr;
          gap: 14px 24px;
        }
        .meta-full { grid-column: 1 / -1; }
        .meta-k {
          font-size: 11px; color: var(--text-subtle);
          text-transform: uppercase;
          letter-spacing: 0.1em;
          margin-bottom: 3px;
        }
        .meta-v { font-size: 13.5px; color: var(--text); }
      `}</style>
    </div>
  );
}

window.IngestReviewScreen = IngestReviewScreen;
