/* StudioApp.jsx — shared chrome + view router */
const { MONITOR, WORKSPACE_TREE } = window.StudioData;

const hexToRgb2 = (hex) => {
  const m = hex.replace('#', '');
  const n = parseInt(m.length === 3 ? m.split('').map(c => c + c).join('') : m, 16);
  return `${(n >> 16) & 255} ${(n >> 8) & 255} ${n & 255}`;
};

function Toasts2({ toasts, dismiss }) {
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

const VIEWS = [
  { id: 'canvas', label: 'Canvas', icon: '◫' },
  { id: 'notebook', label: 'Notebook', icon: '📖' },
  { id: 'monitor', label: 'Monitor', icon: '⚡' },
];

const TWEAK_DEFAULTS_S = /*EDITMODE-BEGIN*/{
  "accent": "#cba6f7",
  "density": "regular"
}/*EDITMODE-END*/;
const ACCENTS_S = ['#cba6f7', '#89b4fa', '#94e2d5', '#fab387'];

function StudioApp() {
  const [t, setTweak] = window.useTweaks(TWEAK_DEFAULTS_S);
  const [view, setView] = React.useState('monitor');
  const [sideTab, setSideTab] = React.useState('workspace');
  const [filter, setFilter] = React.useState('');
  const [toasts, setToasts] = React.useState([]);

  // monitor local state
  const [phaseFilter, setPhaseFilter] = React.useState('all');
  const [logTab, setLogTab] = React.useState('events');

  const pushToast = React.useCallback((toast) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(ts => [...ts, { ...toast, id }]);
    setTimeout(() => {
      setToasts(ts => ts.map(x => x.id === id ? { ...x, leaving: true } : x));
      setTimeout(() => setToasts(ts => ts.filter(x => x.id !== id)), 220);
    }, 3600);
  }, []);
  const dismiss = (id) => setToasts(ts => ts.filter(x => x.id !== id));

  React.useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty('--accent', t.accent);
    r.style.setProperty('--accent-rgb', hexToRgb2(t.accent));
  }, [t.accent]);

  // keep the sidebar tab in sync with the active view
  React.useEffect(() => {
    setSideTab(view === 'notebook' ? 'library' : 'workspace');
  }, [view]);

  const densityClass = t.density === 'compact' ? 'density-compact' : t.density === 'comfy' ? 'density-comfy' : '';

  const tree = WORKSPACE_TREE.filter(n => !filter || n.label.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className={`app ${densityClass}`}>
      {/* ---------- Header ---------- */}
      <div className="hdr">
        <div className="hdr-group">
          <button type="button" className="hdr-ico" title="Menu">☰</button>
          <button type="button" className="hdr-btn">Projects</button>
        </div>
        <div className="hdr-sep"></div>
        <button type="button" className="proj-pick">{MONITOR.project}<span className="car">▾</span></button>
        <button type="button" className="hdr-ico vsc" title="Open in VS Code">⧉</button>
        <button type="button" className="hdr-ico" title="Duplicate">⧉</button>

        <div className="hdr-spacer"></div>

        <div className="viewnav">
          {VIEWS.map(v => (
            <button type="button" key={v.id} className={`vn ${view === v.id ? 'active' : ''}`} onClick={() => setView(v.id)}>
              <span className="gi">{v.icon}</span>{v.label}
            </button>
          ))}
          <button type="button" className={`vn ${view === 'dbx' ? 'active' : ''}`} onClick={() => setView('dbx')}>
            <span className="gi">⛁</span>DB Explorer
          </button>
        </div>

        <div className="hdr-spacer"></div>

        <button type="button" className="hdr-ico" title="Docs">🌐</button>
        <button type="button" className="hdr-ico" title="Theme">☾</button>
        <button type="button" className="hdr-ico" title="Terminal">❯_</button>
        <button type="button" className="publish">Publish</button>
        <div className="winbtns">
          <button type="button" className="winbtn" title="Minimize">─</button>
          <button type="button" className="winbtn" title="Maximize">▢</button>
          <button type="button" className="winbtn close" title="Close">✕</button>
        </div>
      </div>

      {/* ---------- Body ---------- */}
      <div className="body">
        {/* Sidebar */}
        <div className="side">
          <div className="side-tabs">
            <button type="button" className={`side-tab ${sideTab === 'workspace' ? 'active' : ''}`} onClick={() => setSideTab('workspace')}>Workspace</button>
            <button type="button" className={`side-tab ${sideTab === 'library' ? 'active' : ''}`} onClick={() => setSideTab('library')}>Library</button>
          </div>
          <div className="side-search">
            <input className="input" placeholder="Filter…" value={filter} onChange={e => setFilter(e.target.value)} />
            <button type="button" className="side-collapse" title="Collapse all">⌃</button>
          </div>
          <div className="side-scroll">
            {sideTab === 'workspace' ? (
              <React.Fragment>
                <div className="side-section">Workspace</div>
                {tree.map((n, i) => (
                  <button type="button" key={i} className="tree-row">
                    <span className="tw">▸</span>
                    <span className="tg">{n.open ? '◆' : '◇'}</span>
                    {n.label}
                    {n.tag && <span className="ttag">[{n.tag}]</span>}
                  </button>
                ))}
                <div style={{ height: 8 }}></div>
                <button type="button" className={`tree-row nav ${view === 'monitor' ? 'active' : ''}`} onClick={() => setView('monitor')}>
                  <span className="tw"></span><span className="tg">⚡</span>Monitor
                </button>
                <button type="button" className={`tree-row nav ${view === 'dbx' ? 'active' : ''}`} onClick={() => setView('dbx')}>
                  <span className="tw"></span><span className="tg">⛁</span>DB Explorer
                </button>
                <button type="button" className="tree-row nav"><span className="tw"></span><span className="tg">⚙</span>Settings</button>
              </React.Fragment>
            ) : (
              <React.Fragment>
                <div className="side-section">Skills</div>
                <button type="button" className={`tree-row nav ${view === 'notebook' ? 'active' : ''}`} onClick={() => setView('notebook')}>
                  <span className="tw"></span><span className="tg">📖</span>fix/build
                </button>
                <button type="button" className="tree-row"><span className="tw"></span><span className="tg">📖</span>team/build</button>
                <button type="button" className="tree-row"><span className="tw"></span><span className="tg">📖</span>review/gate</button>
              </React.Fragment>
            )}
          </div>
          <div className="side-foot">
            <div className="avatar">SH</div>
            <div className="who">
              <div className="nm">shammai hamilton</div>
              <div className="em">shammaihamilton@gmail.com</div>
            </div>
            <button type="button" className="so">Sign out</button>
          </div>
        </div>

        {/* Main view */}
        {view === 'monitor' && <window.MonitorView phaseFilter={phaseFilter} setPhaseFilter={setPhaseFilter} logTab={logTab} setLogTab={setLogTab} />}
        {view === 'notebook' && <window.NotebookView />}
        {view === 'dbx' && <window.DBExplorerView pushToast={pushToast} />}
        {view === 'canvas' && (
          <div className="main"><div className="empty" style={{ flex: 1 }}><div className="ei">◫</div><div>Canvas view — not part of this redesign.</div></div></div>
        )}
      </div>

      <Toasts2 toasts={toasts} dismiss={dismiss} />

      <window.TweaksPanel>
        <window.TweakSection label="Appearance" />
        <window.TweakColor label="Accent" value={t.accent} options={ACCENTS_S} onChange={v => setTweak('accent', v)} />
        <window.TweakRadio label="Density" value={t.density} options={['compact', 'regular', 'comfy']} onChange={v => setTweak('density', v)} />
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<StudioApp />);
