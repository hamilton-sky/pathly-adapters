/* monitor-directions.jsx — converged Monitor.
   MonitorMain = your V1 (refined) + a clickable FSM pipeline strip.
   StageConfigBoard = clicking a stage opens a modal to change its
   adapter (CLI) and skill .md. Maps to flow_nodes.adapter + skill_overrides. */

/* stage: agent + adapter (CLI) + skill, with run status */
const PIPE = [
  { key: 'STORM',  agent: 'po',       adapter: 'gemini',  skill: 'pathly-storm.md',  status: 'done' },
  { key: 'PLAN',   agent: 'planner',  adapter: 'claude',  skill: 'pathly-plan.md',   status: 'done' },
  { key: 'BUILD',  agent: 'builder',  adapter: 'claude',  skill: 'pathly-build.md',  status: 'active' },
  { key: 'REVIEW', agent: 'reviewer', adapter: 'codex',   skill: 'pathly-review.md', status: 'queued' },
  { key: 'TEST',   agent: 'tester',   adapter: 'claude',  skill: 'pathly-test.md',   status: 'queued' },
];
const AD = {
  claude:  { label: 'Claude',  cls: 'ad-claude',  ico: 'Sparkles' },
  codex:   { label: 'Codex',   cls: 'ad-codex',   ico: 'SquareCode' },
  copilot: { label: 'Copilot', cls: 'ad-copilot', ico: 'Github' },
  gemini:  { label: 'Gemini',  cls: 'ad-gemini',  ico: 'Rocket' },
};
const DOT = { done: 'var(--green)', active: 'var(--blue)', queued: 'var(--surface2)' };

function LiveTag() {
  return <span className="live-tag"><span className="pulse"></span>live</span>;
}

function AdapterBadge({ adapter }) {
  const a = AD[adapter];
  return <span className={`ad-badge ${a.cls}`}><Icon name={a.ico} size={11} />{a.label}</span>;
}

/* clickable FSM pipeline strip */
function PipelineStrip({ activeKey = 'BUILD' }) {
  return (
    <>
      <div className="rd-pipe">
        {PIPE.map((s, i) => (
          <React.Fragment key={s.key}>
            <button type="button" className={`rd-pnode ${s.status} ${s.key === activeKey ? 'active' : ''}`}>
              <div className="pn-top">
                <span className="pn-dot" style={{ background: DOT[s.status] }}></span>
                <span className="pn-name">{s.key}</span>
                <span className="pn-gear"><Icon name="Settings2" size={13} /></span>
              </div>
              <div className="pn-row">
                <Icon name="Bot" size={12} /><span className="pn-agent">{s.agent}</span>
                <AdapterBadge adapter={s.adapter} />
              </div>
              <div className="pn-skill">{s.skill}</div>
            </button>
            {i < PIPE.length - 1 && (
              <div className={`rd-pconn ${PIPE[i].status === 'done' ? 'done' : ''}`}>
                <Icon name="ChevronRight" size={16} />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
      <div className="rd-pipe-hint"><Icon name="MousePointerClick" size={13} />Click any stage to change its CLI or skill — applies to this run or every run.</div>
    </>
  );
}

function Stats() {
  return (
    <div className="mon-stats">
      <div className="mon-stat"><div className="v">486.2k</div><div className="k">Tokens</div></div>
      <div className="mon-stat"><div className="v">21m 04s</div><div className="k">Wall</div></div>
      <div className="mon-stat"><div className="v cost">$4.18</div><div className="k">Cost</div></div>
      <div className="mon-stat"><div className="v">63</div><div className="k">Events</div></div>
    </div>
  );
}

const EVENTS = [
  { type: 'AGENT_DONE', agent: 'builder', n: 3, result: 'PASS', tools: '21 tools', wall: '7m12s', tok: '142k', cost: '$1.21' },
  { type: 'GATE', agent: 'reviewer', action: 'review-gate · PASS', mark: true },
  { type: 'AGENT_DONE', agent: 'reviewer', n: 2, result: 'FAIL', tools: '14 tools', wall: '3m02s', tok: '78k', cost: '$0.64' },
  { type: 'PHASE', agent: 'BUILD', action: 'phase start' },
  { type: 'AGENT_DONE', agent: 'builder', n: 2, result: 'PASS', tools: '29 tools', wall: '9m48s', tok: '130k', cost: '$1.08' },
];

function EventLog() {
  return (
    <div className="elog">
      {EVENTS.map((e, i) => e.type === 'AGENT_DONE' ? (
        <div className="elog-row" key={i}>
          <span className="ts">14:0{9 - i}:21</span>
          <span className={`etype agent_done ${/pass/i.test(e.result) ? 'pass' : ''}`}>AGENT_DONE</span>
          <span className="edetail">
            <span className="ag">{e.agent} #{e.n}</span>
            <span className={`rs ${e.result.toLowerCase()}`}>{e.result}</span>
            <span className="dim">{e.tools}</span><span className="dim">{e.wall}</span>
            <span className="dim">{e.tok}</span><span className="cost">{e.cost}</span>
          </span>
        </div>
      ) : (
        <div className="elog-row" key={i}>
          <span className="ts">14:0{9 - i}:21</span>
          <span className={`etype ${e.type === 'GATE' ? 'gate' : 'phase'}`}>{e.type}</span>
          <span className="edetail">
            <span className="ag" style={{ color: 'var(--text-secondary)' }}>{e.agent}</span>
            <span className="dim">{e.action}</span>
            {e.mark && <Icon name="Check" size={13} style={{ color: 'var(--green)' }} />}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ============ Converged Monitor ============ */
function MonitorMain({ chat = true, blocked = false }) {
  return (
    <StudioShell view="monitor" runBar blocked={blocked} chatOpen={chat}
      sidebar={<MonitorSidebar />} chat={chat ? <ChatDock /> : null}>
      <div className="main">
        <div className="mon-scroll">
          <div className="mon-head"><h1>skill-notebook-editor</h1><LiveTag /></div>
          <div className="mon-section">
            <div className="mon-conv-head"><span className="lbl">Conversations</span><span className="ct">2 / 4</span></div>
            <div className="conv-bar"><div className="seg" style={{ width: '50%' }}></div></div>
            <div style={{ height: 14 }}></div>
            <PipelineStrip />
            <Stats />
            <div className="mon-tabs">
              <button type="button" className="mon-tab active">Events</button>
              <button type="button" className="mon-tab">Output</button>
            </div>
            <div className="eventlog-head">
              <span className="t">Event Log</span>
              <span className="phase-filter">all phases <Icon name="ChevronDown" size={12} /></span>
            </div>
            <EventLog />
          </div>
        </div>
      </div>
    </StudioShell>
  );
}

/* ============ Stage config modal (over the monitor) ============ */
function StageConfigBoard() {
  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <MonitorMain />
      <div className="scrim" style={{ position: 'absolute' }}>
        <div className="modal rd-stagemodal">
          <div className="modal-head">
            <span className="mh-stage" style={{ background: 'color-mix(in srgb, var(--blue) 18%, transparent)', color: 'var(--blue)' }}>B</span>
            <div>
              <div className="mh-name">BUILD stage</div>
              <div className="mh-meta"><span>team flow</span><b>conv 2 · running</b></div>
            </div>
            <span className="spacer"></span>
            <button type="button" className="icon-btn"><Icon name="X" size={16} /></button>
          </div>

          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div>
              <p className="tab-title">Adapter · CLI</p>
              <div className="rd-radio">
                {[['claude', 'fastest, default'], ['codex', 'strict reviews'], ['copilot', 'GitHub native'], ['gemini', 'long context']].map(([k, sub]) => {
                  const a = AD[k]; const on = k === 'claude';
                  return (
                    <button type="button" key={k} className={on ? 'on' : ''}>
                      <span className="ra-ico" style={{ background: `color-mix(in srgb, var(--${k === 'claude' ? 'peach' : k === 'codex' ? 'green' : k === 'copilot' ? 'blue' : 'mauve'}) 18%, transparent)`, color: `var(--${k === 'claude' ? 'peach' : k === 'codex' ? 'green' : k === 'copilot' ? 'blue' : 'mauve'})` }}>
                        <Icon name={a.ico} size={15} />
                      </span>
                      <span>{a.label}<span className="ra-sub">{sub}</span></span>
                      {on && <Icon name="Check" size={15} className="ra-check" />}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="tab-title">Skill</p>
              <div className="rd-selectbox">
                <Icon name="BookOpen" size={15} style={{ color: 'var(--text-muted)' }} />
                <span className="sbmono">pathly-build.md</span>
                <span className="badge sbtag" style={{ '--b-c': 'var(--overlay1)' }}>GLOBAL</span>
                <Icon name="ChevronDown" size={14} style={{ color: 'var(--text-faint)' }} />
              </div>
              <div className="rd-note"><Icon name="Info" size={13} className="ni" />A local <code style={{ fontFamily: 'var(--mono)' }}>my-build.md</code> in this project would override the global automatically.</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <p className="tab-title">Agent role</p>
                <div className="rd-selectbox"><Icon name="Bot" size={15} style={{ color: 'var(--text-muted)' }} /><span>builder</span><Icon name="ChevronDown" size={14} style={{ color: 'var(--text-faint)', marginLeft: 'auto' }} /></div>
              </div>
              <div>
                <p className="tab-title">Max cost / run</p>
                <div className="rd-selectbox"><span style={{ color: 'var(--green)' }}>$</span><span className="sbmono">2.00</span></div>
              </div>
            </div>

            <div>
              <p className="tab-title">Apply to</p>
              <div className="rd-scope">
                <button type="button" className="on">This run only</button>
                <button type="button">Every run (edit flow)</button>
              </div>
            </div>
          </div>

          <div className="modal-ctrl" style={{ justifyContent: 'flex-end', gap: 10, borderTop: '1px solid var(--border)', borderBottom: 'none' }}>
            <button type="button" className="btn ghost">Cancel</button>
            <button type="button" className="publish" style={{ height: 32 }}>Apply to BUILD</button>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MonitorMain, StageConfigBoard, PipelineStrip });
