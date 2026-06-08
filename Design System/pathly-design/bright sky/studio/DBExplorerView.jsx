/* DBExplorerView.jsx — DB Explorer as a routed view inside Studio shell.
   Reuses window.DBData + window.FeatureModal. */
const DBX = window.DBData;

function MiniPath2({ path }) {
  const seq = path.length > 7 ? path.slice(path.length - 7) : path;
  return (
    <div className="mini-path">
      {seq.map((s, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="mini-sep">›</span>}
          <span className="mini-pill" style={{ width: 14 + s.length, '--mp-c': DBX.stageVar(s) }} title={s}></span>
        </React.Fragment>
      ))}
    </div>
  );
}
function pathFor2(name) {
  const evs = DBX.EVENTS_BY_FEATURE[name] || [];
  return evs.filter(e => e.type === 'STATE_TRANSITION').slice().sort((a, b) => a.seq - b.seq).map(e => e.payload.to);
}

function DBCard({ f, onOpen }) {
  return (
    <button type="button" className="fcard" onClick={() => onOpen(f)}>
      <div className="fcard-top">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="fcard-name">{f.name}</span>
          <span className={`badge ${DBX.stageClass(f.state)}`}><span className="bd"></span>{f.state}</span>
        </div>
        <span className="fcard-open">↗</span>
      </div>
      <MiniPath2 path={pathFor2(f.name)} />
      <div className="fcard-stats">
        <div className="fc-stat"><span className="l">Events</span><span className="n">{f.event_count}</span></div>
        <div className="fc-stat"><span className="l">Invocations</span><span className="n">{f.agent_done_count}</span></div>
        <div className="fc-stat"><span className="l">Tokens</span><span className="n">{DBX.fmtNum(f.total_tokens)}</span></div>
        <div className="fc-stat"><span className="l">Cost</span><span className="n cost">{DBX.fmtMoney(f.total_cost_usd)}</span></div>
      </div>
      <div className="fcard-foot">
        <span className="ts">{DBX.fmtTime(f.last_event_ts)}</span>
        <div className="conv-prog">
          <div className="track"><div className="fill" style={{ width: `${(f.convs_done / f.convs_total) * 100 || 0}%` }}></div></div>
          <span className="lbl">{f.convs_done}/{f.convs_total}</span>
        </div>
      </div>
    </button>
  );
}

function DBExplorerView({ pushToast }) {
  const [open, setOpen] = React.useState(null);
  const S = DBX.SUMMARY;
  const runMigration = () => pushToast({ kind: 'green', title: 'Migration complete', msg: `${S.features} features migrated · ${S.events} events written` });
  const refresh = () => pushToast({ kind: 'blue', title: 'Refreshed', msg: `${S.features} features · ${S.events} events` });
  const exportAll = () => {
    const all = {}; DBX.FEATURES.forEach(f => { all[f.name] = DBX.EVENTS_BY_FEATURE[f.name]; });
    const blob = new Blob([JSON.stringify(all, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = 'pathly-all-events.json'; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    pushToast({ kind: 'green', title: 'Export started', msg: `pathly-all-events.json (${S.events} events)` });
  };

  const stats = [
    { k: 'Features', v: S.features, c: 'var(--blue)' },
    { k: 'Events', v: DBX.fmtNum(S.events), c: 'var(--green)' },
    { k: 'Invocations', v: S.invocations, c: 'var(--mauve)' },
    { k: 'Total cost', v: DBX.fmtMoney(S.total_cost), c: 'var(--peach)' },
  ];

  return (
    <div className="main">
      <div className="panel-body" style={{ flex: 1 }}>
        <div className="dbx-head">
          <div className="dbx-title">
            <h1>DB Explorer</h1>
            <div className="sub">Pipeline databases · <code>pathly/plans/*/pathly.db</code> · FSM server <code>127.0.0.1:8765</code></div>
          </div>
          <div className="ctrl-bar">
            <button type="button" className="btn" onClick={refresh}><span className="gi">↻</span> Refresh</button>
            <button type="button" className="btn" onClick={runMigration}><span className="gi">⬇</span> Run Migration</button>
            <button type="button" className="btn" onClick={exportAll}><span className="gi">⤓</span> Export JSON</button>
          </div>
        </div>
        <div className="summary-strip">
          {stats.map(s => (
            <div className="stat-chip" key={s.k} style={{ '--chip-c': s.c }}>
              <span className="k">{s.k}</span><span className="v">{s.v}</span>
            </div>
          ))}
        </div>
        <div className="card-grid">
          {DBX.FEATURES.map(f => <DBCard key={f.name} f={f} onOpen={setOpen} />)}
        </div>
      </div>
      {open && <window.FeatureModal feature={open} onClose={() => setOpen(null)} pushToast={pushToast} />}
    </div>
  );
}

window.DBExplorerView = DBExplorerView;
