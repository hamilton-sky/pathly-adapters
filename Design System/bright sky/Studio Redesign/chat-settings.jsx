/* chat-settings.jsx — ChatDock (HQ initiation surface) + SettingsView
   (palette picker like the real Settings, routing engine, runner config). */

/* ---------- Chat dock (HQ) ---------- */
function ChatDock() {
  return (
    <div className="rd-chat">
      <div className="rd-chat-head">
        <div className="rd-chat-title"><Icon name="Sparkles" size={15} style={{ color: 'var(--accent)' }} />Pathly</div>
        <div className="rd-chat-tabs">
          <span className="rd-chat-tab on"><Icon name="Sparkles" size={11} />Claude</span>
          <span className="rd-chat-tab"><Icon name="SquareCode" size={11} />Codex</span>
          <span className="rd-chat-tab"><Icon name="SquareTerminal" size={11} />Shell</span>
        </div>
        <button type="button" className="hdr-ico" title="Close"><Icon name="X" size={15} /></button>
      </div>

      <div className="rd-chat-body">
        <div className="rd-msg bot">What should we build? Describe a task and I'll match it to a skill or flow.</div>
        <div className="rd-msg user">add rate limiting to the login endpoint</div>

        <div className="rd-card">
          <div className="cardh"><Icon name="Wand" size={13} />Matched skill</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon name="BookOpen" size={15} style={{ color: 'var(--blue)' }} />
            <span className="rd-mc-skill">pathly-build</span>
            <span className="rd-mc-conf">92% match</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>Plan → build → review → test on <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-secondary)' }}>team</span> flow.</div>
          <div className="rd-mc-actions">
            <button type="button" className="publish" style={{ height: 30 }}><Icon name="Play" size={12} style={{ marginRight: 5 }} />Run</button>
            <button type="button" className="btn sm">Alternatives</button>
            <button type="button" className="btn ghost sm">Reject</button>
          </div>
        </div>

        <div className="rd-card" style={{ borderColor: 'color-mix(in srgb, var(--accent) 30%, transparent)' }}>
          <div className="cardh"><Icon name="ListChecks" size={13} />Automation · 4 steps</div>
          <div style={{ fontSize: 12.5, color: 'var(--text-secondary)' }}>storm → plan → build → review</div>
          <div className="rd-mc-actions">
            <button type="button" className="btn sm primary">Run all</button>
            <button type="button" className="btn sm">Step by step</button>
          </div>
        </div>

        <div className="rd-msg bot" style={{ display: 'flex', alignItems: 'center', gap: 8, fontStyle: 'italic', color: 'var(--text-muted)' }}>
          <span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--accent)' }}></span>thinking — matching intent…
        </div>
      </div>

      <div className="rd-chat-input">
        <div className="rd-chat-field">
          <Icon name="MessageSquare" size={15} style={{ color: 'var(--text-faint)' }} />
          <input placeholder="Ask Pathly or describe a task…" />
        </div>
        <div className="rd-chat-foot">
          <span className="rd-model"><Icon name="Cpu" size={12} />Claude Sonnet 4.5<Icon name="ChevronDown" size={12} /></span>
          <span className="rd-model"><Icon name="Zap" size={12} />Auto</span>
          <button type="button" className="rd-send"><Icon name="ArrowUp" size={16} /></button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Settings ---------- */
const DARK_SW = [
  { id: 'dark', label: 'Pathly Dark', bg: '#111827', a: '#38BDF8', b: '#34D399' },
  { id: 'nord', label: 'Nord', bg: '#2e3440', a: '#88c0d0', b: '#a3be8c' },
  { id: 'mocha', label: 'Mocha', bg: '#1e1e2e', a: '#cba6f7', b: '#a6e3a1' },
  { id: 'solarized', label: 'Solarized', bg: '#002b36', a: '#268bd2', b: '#859900' },
  { id: 'dracula', label: 'Dracula', bg: '#282a36', a: '#bd93f9', b: '#50fa7b' },
  { id: 'rose-pine', label: 'Rosé Pine', bg: '#191724', a: '#c4a7e7', b: '#9ccfd8' },
];
const LIGHT_SW = [
  { id: 'light', label: 'Pathly Light', bg: '#F8FAFC', a: '#0369A1', b: '#047857' },
  { id: 'solarized-light', label: 'Sol. Light', bg: '#fdf6e3', a: '#268bd2', b: '#859900' },
  { id: 'latte', label: 'Latte', bg: '#eff1f5', a: '#8839ef', b: '#40a02b' },
  { id: 'paper', label: 'Paper', bg: '#ffffff', a: '#c75c2a', b: '#16a34a' },
  { id: 'rose-pine-dawn', label: 'Dawn', bg: '#faf4ed', a: '#b4637a', b: '#286983' },
  { id: 'mint', label: 'Mint', bg: '#f0faf5', a: '#0891b2', b: '#0f7d52' },
];

function Swatch({ s, on }) {
  return (
    <div className={`rd-swatch ${on ? 'on' : ''}`}>
      <div className="sw-prev" style={{ background: s.bg }}>
        <div className="sw-bar" style={{ background: s.a, height: 22 }}></div>
        <div className="sw-bar" style={{ background: s.b, height: 14 }}></div>
        <div className="sw-bar" style={{ background: 'color-mix(in srgb, ' + s.a + ' 30%, transparent)', height: 30 }}></div>
      </div>
      <div className="sw-name">{s.label}</div>
    </div>
  );
}

function SettingsView({ activeDark = 'dark', activeLight = 'light' }) {
  return (
    <div className="rd-set">
      <div className="rd-set-scroll">
        <div className="rd-set-head">Settings</div>
        <div className="rd-set-body">

          <div className="rd-set-sec">
            <div className="st">Color palette</div>
            <div className="sh">Pick your preferred <strong>dark</strong> and <strong>light</strong> palette — the ☽ / ☀ toggle in the top bar switches between them.</div>
            <div className="rd-set-grp">Dark — <b>Pathly Dark</b></div>
            <div className="rd-swrow">{DARK_SW.map(s => <Swatch key={s.id} s={s} on={s.id === activeDark} />)}</div>
            <div className="rd-set-grp" style={{ marginTop: 16 }}>Light — <b>Pathly Light</b></div>
            <div className="rd-swrow">{LIGHT_SW.map(s => <Swatch key={s.id} s={s} on={s.id === activeLight} />)}</div>
          </div>

          <div className="rd-set-sec">
            <div className="st">Routing engine</div>
            <div className="sh">How pipeline stages are chosen and sequenced.</div>
            <div className="rd-radio2">
              <div className="rd-rcard on"><div className="rl"><Icon name="Sparkles" size={15} style={{ color: 'var(--accent)' }} />LLM driven</div><div className="rd2">Orchestrator agent reads the flow YAML and routes</div></div>
              <div className="rd-rcard"><div className="rl"><Icon name="Workflow" size={15} style={{ color: 'var(--text-muted)' }} />Python FSM</div><div className="rd2">Deterministic FSM over HTTP</div></div>
            </div>
          </div>

          <div className="rd-set-sec">
            <div className="st">Runner</div>
            <div className="sh">How stages launch. Applies to the next run.</div>
            <div className="rd-radio2" style={{ marginBottom: 16 }}>
              <div className="rd-rcard on"><div className="rl"><Icon name="SquareTerminal" size={15} style={{ color: 'var(--accent)' }} />Interactive</div><div className="rd2">Visible PTY — killed when AGENT_DONE fires</div></div>
              <div className="rd-rcard"><div className="rl"><Icon name="EyeOff" size={15} style={{ color: 'var(--text-muted)' }} />Headless</div><div className="rd2">Background run — waits for natural PTY exit</div></div>
            </div>
            <div className="rd-set-fields">
              <div className="rd-set-field"><span className="fl">Max cost (USD)</span><span className="fi">$2.00</span></div>
              <div className="rd-set-field"><span className="fl">Max iterations</span><span className="fi">12</span></div>
              <button type="button" className="btn sm">Save</button>
            </div>
          </div>

          <div className="rd-set-sec" style={{ borderBottom: 'none' }}>
            <div className="st">Adapters</div>
            <div className="sh">CLI path per AI host. Used when a stage routes to that adapter.</div>
            <div className="rd-set-fields" style={{ gap: 18 }}>
              {[['Claude', 'Sparkles'], ['Codex', 'SquareCode'], ['Copilot', 'Github'], ['Antigravity', 'Rocket']].map(([n, ic]) => (
                <div className="rd-set-field" key={n}><span className="fl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon name={ic} size={13} />{n}</span><span className="fi" style={{ width: 130, fontSize: 12 }}>/usr/bin/{n.toLowerCase()}</span></div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function SettingsBoard() {
  return (
    <StudioShell view="dbx" runBar sidebar={<MonitorSidebar active="" />} chat={null}>
      <SettingsView />
    </StudioShell>
  );
}

Object.assign(window, { ChatDock, SettingsView, SettingsBoard });
