/* App.jsx — Studio shell, summary strip, card grid, toasts, tweaks */
const {
  FEATURES, SUMMARY, getState,
  stageClass, stageVar, fmtMoney, fmtNum, fmtTime,
} = window.DBData;

const hexToRgb = (hex) => {
  const m = hex.replace('#', '');
  const n = parseInt(m.length === 3 ? m.split('').map(c => c + c).join('') : m, 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
};

/* ---- mini state path for cards ---- */
function MiniPath({ path }) {
  // condense to last ~7 states for the card
  const seq = path.length > 7 ? path.slice(path.length - 7) : path;
  return (
    <div className="mini-path">
      {seq.map((s, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="mini-sep">›</span>}
          <span className="mini-pill" style={{ width: 14 + s.length, '--mp-c': stageVar(s) }} title={s}></span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* state path per feature (for mini-path) — derive from events */
function pathFor(name) {
  const evs = window.DBData.EVENTS_BY_FEATURE[name] || [];
  return evs.filter(e => e.type === 'STATE_TRANSITION').slice().sort((a, b) => a.seq - b.seq).map(e => e.payload.to);
}

function FeatureCard({ f, onOpen }) {
  return (
    <button type="button" className="fcard" onClick={() => onOpen(f)}>
      <div className="fcard-top">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="fcard-name">{f.name}</span>
          <span className={`badge ${stageClass(f.state)}`}><span className="bd"></span>{f.state}</span>
        </div>
        <span className="fcard-open">↗</span>
      </div>
      <MiniPath path={pathFor(f.name)} />
      <div className="fcard-stats">
        <div className="fc-stat"><span className="l">Events</span><span className="n">{f.event_count}</span></div>
        <div className="fc-stat"><span className="l">Invocations</span><span className="n">{f.agent_done_count}</span></div>
        <div className="fc-stat"><span className="l">Tokens</span><span className="n">{fmtNum(f.total_tokens)}</span></div>
        <div className="fc-stat"><span className="l">Cost</span><span className="n cost">{fmtMoney(f.total_cost_usd)}</span></div>
      </div>
      <div className="fcard-foot">
        <span className="ts">{fmtTime(f.last_event_ts)}</span>
        <div className="conv-prog">
          <div className="track"><div className="fill" style={{ width: `${(f.convs_done / f.convs_total) * 100 || 0}%` }}></div></div>
          <span className="lbl">{f.convs_done}/{f.convs_total}</span>
        </div>
      </div>
    </button>
  );
}

/* ---- Split layout (alternate direction) ---- */
function SplitView({ features, pushToast }) {
  const [sel, setSel] = React.useState(features[0]);
  return (
    <div className="split">
      <div className="split-list">
        {features.map(f => (
          <button type="button" key={f.name} className={`split-row ${sel.name === f.name ? 'active' : ''}`} onClick={() => setSel(f)}>
            <span className="sr-name">{f.name}</span>
            <span className={`badge ${stageClass(f.state)}`} style={{ alignSelf: 'flex-start' }}><span className="bd"></span>{f.state}</span>
            <span className="sr-sub">{f.event_count} events · {fmtMoney(f.total_cost_usd)}</span>
          </button>
        ))}
      </div>
      <div className="split-main">
        <window.FeatureDetail key={sel.name} feature={sel} pushToast={pushToast} />
      </div>
    </div>
  );
}

/* ---- Toasts ---- */
function Toasts({ toasts, dismiss }) {
  return (
    <div className="toast-stack">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-c-${t.kind || 'blue'} ${t.leaving ? 'leaving' : ''}`}>
          <span className="ti">{t.kind === 'red' ? '⚠' : t.kind === 'green' ? '✓' : 'ℹ'}</span>
          <div className="tc">
            <div className="tt">{t.title}</div>
            {t.msg && <div className="tm">{t.msg}</div>}
          </div>
          <button type="button" className="icon-btn" style={{ width: 22, height: 22, fontSize: 12 }} onClick={() => dismiss(t.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#cba6f7",
  "density": "regular",
  "layout": "cards"
}/*EDITMODE-END*/;

const ACCENTS = ['#cba6f7', '#89b4fa', '#94e2d5', '#fab387'];

function App() {
  const [t, setTweak] = window.useTweaks(TWEAK_DEFAULTS);
  const [open, setOpen] = React.useState(null);
  const [toasts, setToasts] = React.useState([]);
  const [lastRefresh, setLastRefresh] = React.useState(Date.now());

  const pushToast = React.useCallback((toast) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(ts => [...ts, { ...toast, id }]);
    setTimeout(() => {
      setToasts(ts => ts.map(x => x.id === id ? { ...x, leaving: true } : x));
      setTimeout(() => setToasts(ts => ts.filter(x => x.id !== id)), 220);
    }, 3600);
  }, []);
  const dismiss = (id) => setToasts(ts => ts.filter(x => x.id !== id));

  // apply accent + density
  React.useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty('--accent', t.accent);
    r.style.setProperty('--accent-rgb', hexToRgb(t.accent));
  }, [t.accent]);

  const densityClass = t.density === 'compact' ? 'density-compact' : t.density === 'comfy' ? 'density-comfy' : '';

  const refreshAll = () => {
    setLastRefresh(Date.now());
    pushToast({ kind: 'blue', title: 'Refreshed', msg: `${SUMMARY.features} features · ${SUMMARY.events} events` });
  };
  const runMigration = () => {
    pushToast({ kind: 'green', title: 'Migration complete', msg: `${SUMMARY.features} features migrated · ${SUMMARY.events} events written` });
  };
  const exportAll = () => {
    const all = {};
    FEATURES.forEach(f => { all[f.name] = window.DBData.EVENTS_BY_FEATURE[f.name]; });
    const blob = new Blob([JSON.stringify(all, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `pathly-all-events.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    pushToast({ kind: 'green', title: 'Export started', msg: `pathly-all-events.json (${SUMMARY.events} events)` });
  };

  const stats = [
    { k: 'Features', v: SUMMARY.features, c: 'var(--blue)' },
    { k: 'Events', v: fmtNum(SUMMARY.events), c: 'var(--green)' },
    { k: 'Invocations', v: SUMMARY.invocations, c: 'var(--mauve)' },
    { k: 'Total cost', v: fmtMoney(SUMMARY.total_cost), c: 'var(--peach)' },
  ];

  return (
    <div className={`studio ${densityClass}`}>
      {/* App rail */}
      <div className="rail">
        <div className="rail-logo">P</div>
        <button type="button" className="rail-ico" title="Plans">◫</button>
        <button type="button" className="rail-ico" title="Monitor">◷</button>
        <button type="button" className="rail-ico active" title="DB Explorer">⛁</button>
        <button type="button" className="rail-ico" title="HQ">⊞</button>
        <div className="rail-spacer"></div>
        <button type="button" className="rail-ico" title="Settings">⚙</button>
      </div>

      <div className="workspace">
        {/* Panel tabs */}
        <div className="panel-tabs">
          <div className="win-dots">
            <span className="win-dot" style={{ background: 'var(--red)' }}></span>
            <span className="win-dot" style={{ background: 'var(--yellow)' }}></span>
            <span className="win-dot" style={{ background: 'var(--green)' }}></span>
          </div>
          <button type="button" className="panel-tab"><span className="dot"></span>Monitor</button>
          <button type="button" className="panel-tab"><span className="dot"></span>HQ</button>
          <button type="button" className="panel-tab active"><span className="dot"></span>DB Explorer</button>
          <div className="panel-tabs-spacer"></div>
        </div>

        {/* Panel body */}
        <div className="panel-body">
          <div className="dbx-head">
            <div className="dbx-title">
              <h1>DB Explorer</h1>
              <div className="sub">Pipeline databases · <code>pathly/plans/*/pathly.db</code> · FSM server <code>127.0.0.1:8765</code></div>
            </div>
            <div className="ctrl-bar">
              <button type="button" className="btn" onClick={refreshAll}><span className="gi">↻</span> Refresh</button>
              <button type="button" className="btn" onClick={runMigration}><span className="gi">⬇</span> Run Migration</button>
              <button type="button" className="btn" onClick={exportAll}><span className="gi">⤓</span> Export JSON</button>
            </div>
          </div>

          {/* Summary strip */}
          <div className="summary-strip">
            {stats.map(s => (
              <div className="stat-chip" key={s.k} style={{ '--chip-c': s.c }}>
                <span className="k">{s.k}</span>
                <span className="v">{s.v}</span>
              </div>
            ))}
          </div>

          {/* Layout: cards or split */}
          {t.layout === 'split'
            ? <SplitView features={FEATURES} pushToast={pushToast} />
            : (
              <div className="card-grid">
                {FEATURES.map(f => <FeatureCard key={f.name} f={f} onOpen={setOpen} />)}
              </div>
            )}
        </div>
      </div>

      {open && <window.FeatureModal feature={open} onClose={() => setOpen(null)} pushToast={pushToast} />}
      <Toasts toasts={toasts} dismiss={dismiss} />

      {/* Tweaks */}
      <window.TweaksPanel>
        <window.TweakSection label="Appearance" />
        <window.TweakColor label="Accent" value={t.accent} options={ACCENTS} onChange={v => setTweak('accent', v)} />
        <window.TweakRadio label="Density" value={t.density} options={['compact', 'regular', 'comfy']} onChange={v => setTweak('density', v)} />
        <window.TweakSection label="Layout" />
        <window.TweakRadio label="Direction" value={t.layout} options={['cards', 'split']} onChange={v => setTweak('layout', v)} />
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
