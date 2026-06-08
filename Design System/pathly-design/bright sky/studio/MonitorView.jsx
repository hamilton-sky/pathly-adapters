/* MonitorView.jsx — redesigned Monitor page */
const M = window.StudioData.MONITOR;

const CHANNEL_COLOR = {
  Health: 'var(--green)', FSM: 'var(--blue)', State: 'var(--mauve)',
  Feedback: 'var(--peach)', Events: 'var(--teal)',
};

function FsmStepper({ stages }) {
  return (
    <div className="stepper">
      {stages.map((s, i) => (
        <React.Fragment key={s.key}>
          <div className={`step ${s.status}`}>
            <div className="node"></div>
            <div className="slbl">{s.short}</div>
          </div>
          {i < stages.length - 1 && (
            <div className={`step-link ${stages[i].status === 'done' ? 'done' : ''}`}></div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function EventRow({ e }) {
  if (e.type === 'AGENT_DONE') {
    const pass = /pass|done/i.test(e.result);
    return (
      <div className="elog-row">
        <span className="ts">{e.ts}</span>
        <span className={`etype agent_done ${pass ? 'pass' : ''}`}>AGENT_DONE</span>
        <span className="edetail">
          <span className="ag">{e.agent} #{e.n}</span>
          <span className={`rs ${e.result.toLowerCase()}`}>{e.result}</span>
          <span className="dim">{e.tools} tools</span>
          <span className="dim">{e.wall}</span>
          <span className="dim">{e.tok}</span>
          <span className="cost">{e.cost}</span>
        </span>
      </div>
    );
  }
  const isType = e.type === 'GATE' ? 'gate' : 'phase';
  return (
    <div className="elog-row">
      <span className="ts">{e.ts}</span>
      <span className={`etype ${isType}`}>{e.type}</span>
      <span className="edetail">
        <span className="ag" style={{ color: 'var(--text-secondary)' }}>{e.agent}</span>
        <span className="dim">{e.action}</span>
        <span className={`mk ${e.mark === '✓' ? 'ok' : ''}`}>{e.mark}</span>
      </span>
    </div>
  );
}

function MonitorView({ phaseFilter, setPhaseFilter, logTab, setLogTab }) {
  const events = phaseFilter === 'all'
    ? M.events
    : M.events.filter(e => (e.type || '').toLowerCase() === phaseFilter);

  return (
    <div className="main">
      {/* doc tabs */}
      <div className="doctabs">
        <button type="button" className="doctab-arrow">‹</button>
        {M.tabs.map((t, i) => (
          <button type="button" key={i} className={`doctab ${t.active ? 'active' : ''}`}>
            {t.name.length > 20 ? t.name.slice(0, 20) + '…' : t.name}
            {t.dirty && <span className="dt-dot"></span>}
          </button>
        ))}
        <span className="doctab-nav">{M.tab_pos}</span>
        <button type="button" className="doctab-arrow">›</button>
      </div>

      <div className="mon-scroll">
        <div className="mon-head">
          <h1>{M.project}</h1>
          {M.live && <span className="live-tag"><span className="pulse"></span>live</span>}
        </div>

        <div className="mon-section">
          <div className="mon-conv-head">
            <span className="lbl">Conversations</span>
            <span className="ct">{M.convs_done}/{M.convs_total} ▾</span>
          </div>
          <div className="conv-bar"><div className="seg" style={{ width: `${(M.convs_done / M.convs_total) * 100}%` }}></div></div>

          <div className="mon-legend">
            {M.channels.map((c, i) => (
              <span key={c} className={`lg ${i === 0 ? 'head' : ''}`}>
                <span className="d" style={{ background: CHANNEL_COLOR[c] }}></span>{c}
              </span>
            ))}
          </div>

          <div className="mon-sub">conv {M.conv_index} · <b>{M.steps_done} done</b> · {M.steps_remaining} remaining</div>

          <FsmStepper stages={M.stages} />

          <div className="mon-stats">
            <div className="mon-stat"><div className="v">{M.stats.tokens}</div><div className="k">Tokens</div></div>
            <div className="mon-stat"><div className="v">{M.stats.wall}</div><div className="k">Wall</div></div>
            <div className="mon-stat"><div className="v cost">{M.stats.cost}</div><div className="k">Cost</div></div>
            <div className="mon-stat"><div className="v">{M.stats.events}</div><div className="k">Events</div></div>
          </div>

          <div className="mon-tabs">
            <button type="button" className={`mon-tab ${logTab === 'events' ? 'active' : ''}`} onClick={() => setLogTab('events')}>Events</button>
            <button type="button" className={`mon-tab ${logTab === 'output' ? 'active' : ''}`} onClick={() => setLogTab('output')}>Output</button>
          </div>

          {logTab === 'events' ? (
            <React.Fragment>
              <div className="eventlog-head">
                <span className="t">Event Log</span>
                <select className="phase-filter" value={phaseFilter} onChange={e => setPhaseFilter(e.target.value)}>
                  <option value="all">all phases</option>
                  <option value="agent_done">AGENT_DONE</option>
                  <option value="phase">PHASE</option>
                  <option value="gate">GATE</option>
                </select>
              </div>
              <div className="elog">
                {events.map((e, i) => <EventRow key={i} e={e} />)}
              </div>
              <div className="elog-foot">
                <span className="io">in/out <span>−↑</span> <span>−↓</span></span>
                <span>= {M.combined} ↑</span>
              </div>
            </React.Fragment>
          ) : (
            <div className="elog" style={{ padding: 16, fontFamily: 'var(--mono)', color: 'var(--text-muted)', fontSize: 12.5, lineHeight: 1.7, marginTop: 16 }}>
              <div style={{ color: 'var(--green)' }}>$ pathly run --stage build --feature fsm-server-sqlite</div>
              <div>→ attaching to conv 0 · BUILDING</div>
              <div style={{ color: 'var(--blue)' }}>[builder #2] writing migrate_to_sqlite.py … done (448s)</div>
              <div>[reviewer #2] PASS · 29 tools · 129.8k tok</div>
              <div style={{ color: 'var(--yellow)' }}>[tester #1] 3/12 failing — NULL ts ordering</div>
              <div style={{ color: 'var(--text-faint)' }}>idle · awaiting next phase…</div>
            </div>
          )}
          <div style={{ height: 30 }}></div>
        </div>
      </div>
    </div>
  );
}

window.MonitorView = MonitorView;
