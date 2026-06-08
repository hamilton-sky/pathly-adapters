/* FeatureModal.jsx — feature detail with tab nav + per-feature control bar */
const { EVENTS_BY_FEATURE, getState, getAgents, stageClass, fmtMoney, fmtNum } = window.DBData;

const TABS = ['Timeline', 'Events', 'Agents', 'SQL'];

function FeatureDetail({ feature, pushToast, embedded }) {
  const [tab, setTab] = React.useState('Timeline');
  const [nonce, setNonce] = React.useState(0); // refresh key

  const events = React.useMemo(() => EVENTS_BY_FEATURE[feature.name] || [], [feature.name, nonce]);
  const agents = React.useMemo(() => getAgents(feature.name), [feature.name, nonce]);
  const state = getState(feature.name);

  const counts = {
    Timeline: events.filter(e => e.type === 'STATE_TRANSITION').length,
    Events: events.length,
    Agents: agents.length,
    SQL: null,
  };

  const refresh = () => {
    setNonce(n => n + 1);
    pushToast({ kind: 'blue', title: 'Refreshed', msg: `${feature.name} · ${events.length} events reloaded` });
  };

  const runMigration = () => {
    pushToast({ kind: 'green', title: 'Migration complete', msg: `7 features migrated · 214 events written to sqlite` });
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(events, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${feature.name}-events.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    pushToast({ kind: 'green', title: 'Export started', msg: `${feature.name}-events.json (${events.length} events)` });
  };

  return (
    <React.Fragment>
      {!embedded && (
        <div className="modal-ctrl">
          <button type="button" className="btn sm" onClick={refresh}><span className="gi">↻</span> Refresh</button>
          <button type="button" className="btn sm" onClick={runMigration}><span className="gi">⬇</span> Run Migration</button>
          <button type="button" className="btn sm" onClick={exportJson}><span className="gi">⤓</span> Export JSON</button>
          {state?.runner && (
            <span style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-muted)' }}>
              runner: {state.runner.status} · {fmtNum(state.runner.total_tokens)} tok · {fmtMoney(state.runner.total_cost_usd)}
            </span>
          )}
        </div>
      )}

      <div className="tab-nav">
        {TABS.map(t => (
          <button type="button" key={t} className={`tab-btn ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t}{counts[t] != null && <span className="cnt">{counts[t]}</span>}
          </button>
        ))}
      </div>

      <div className="modal-body">
        {tab === 'Timeline' && <window.Timeline events={events} />}
        {tab === 'Events' && <window.EventsTab events={events} />}
        {tab === 'Agents' && <window.AgentsTab agents={agents} />}
        {tab === 'SQL' && <window.SqlTab pushToast={pushToast} />}
      </div>
    </React.Fragment>
  );
}

function FeatureModal({ feature, onClose, pushToast }) {
  React.useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const state = getState(feature.name);

  return (
    <div className="scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true">
        <div className="modal-head">
          <span className={`badge ${stageClass(feature.state)}`}><span className="bd"></span>{feature.state}</span>
          <span className="mh-name">{feature.name}</span>
          <span className="mh-meta">
            <span>convs <b>{feature.convs_done}/{feature.convs_total}</b></span>
            <span>events <b>{feature.event_count}</b></span>
            <span>cost <b style={{ color: 'var(--green)' }}>{fmtMoney(feature.total_cost_usd)}</b></span>
          </span>
          <span className="spacer"></span>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <FeatureDetail feature={feature} pushToast={pushToast} />
      </div>
    </div>
  );
}

window.FeatureModal = FeatureModal;
window.FeatureDetail = FeatureDetail;
