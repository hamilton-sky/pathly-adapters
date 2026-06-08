/* shell.jsx — shared Pathly Studio chrome + Lucide icon helper.
   Reuses tokens + classes from styles.css + studio.css.
   Icons come from the lucide UMD global (window.lucide.icons), matching the
   real codebase which imports from lucide-react. No emoji anywhere. */

function Icon({ name, size = 16, stroke = 2, style, className }) {
  const lib = (window.lucide && (window.lucide.icons || window.lucide)) || {};
  const node = lib[name];
  const kids = Array.isArray(node) ? node : (node && node.iconNode) || [];
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={{ flex: '0 0 auto', ...style }}>
      {kids.map((c, i) => React.createElement(c[0], { key: i, ...c[1] }))}
    </svg>
  );
}

const VIEWS = [
  { key: 'canvas',   label: 'Canvas',   ico: 'Workflow' },
  { key: 'notebook', label: 'Notebook', ico: 'NotebookText' },
  { key: 'monitor',  label: 'Monitor',  ico: 'Activity' },
  { key: 'dbx',      label: 'DB Explorer', ico: 'Database' },
];

const RUN_PIPE = ['done', 'done', 'active', 'queued', 'queued'];

function RunBar({ blocked }) {
  return (
    <div className="rd-runbar">
      <div className="rd-rb-feat">
        <span className={`dot ${blocked ? 'blocked' : ''}`}></span>skill-notebook-editor
      </div>
      <div className="rd-rb-dots">
        {RUN_PIPE.map((s, i) => <span key={i} className={`rd-rb-pd ${s}`}></span>)}
      </div>
      <span className="rd-rb-cur">BUILD</span>
      <span className="rd-rb-status">{blocked ? 'blocked · review gate' : 'builder #3 · running'}</span>
      <div className="rd-rb-spacer"></div>
      {blocked && (
        <>
          <button type="button" className="rd-rb-decision"><Icon name="ChevronsRight" size={13} />Advance</button>
          <button type="button" className="rd-rb-decision"><Icon name="Shuffle" size={13} />Reroute</button>
          <button type="button" className="rd-rb-decision"><Icon name="RotateCcw" size={13} />Retry</button>
          <div className="rd-rb-sep"></div>
        </>
      )}
      <span className="rd-rb-cost"><span className="lbl">cost</span>$4.18</span>
      <div className="rd-rb-sep"></div>
      <div className="rd-rb-group">
        <button type="button" className={`rd-rb-btn ${blocked ? '' : 'off'}`} title="Start"><Icon name="Play" size={14} /></button>
        <button type="button" className={`rd-rb-btn ${blocked ? 'off' : 'primary'}`} title="Pause"><Icon name="Pause" size={14} /></button>
        <button type="button" className="rd-rb-btn" title="Mode: interactive"><Icon name="SquareTerminal" size={14} /></button>
        <button type="button" className="rd-rb-btn danger" title="Abort"><Icon name="Square" size={13} /></button>
      </div>
    </div>
  );
}

function StudioShell({ view, project = 'C:/auth-service', sidebar, children, runBar, blocked, chat, chatOpen }) {
  return (
    <div className="app" style={{ height: '100%' }}>
      <div className="hdr">
        <div className="hdr-group">
          <button type="button" className="hdr-ico" title="Menu"><Icon name="Menu" size={17} /></button>
          <button type="button" className="hdr-btn"><Icon name="LayoutGrid" size={15} className="gi" />Projects</button>
        </div>
        <div className="hdr-sep"></div>
        <button type="button" className="proj-pick">
          <span>{project}</span><Icon name="ChevronsUpDown" size={13} className="car" />
        </button>
        <div className="hdr-spacer"></div>
        <div className="viewnav">
          {VIEWS.map(v => (
            <button type="button" key={v.key} className={`vn ${v.key === view ? 'active' : ''}`}>
              <Icon name={v.ico} size={14} className="gi" />{v.label}
            </button>
          ))}
        </div>
        <div className="hdr-spacer"></div>
        <button type="button" className={`hdr-ico ${chatOpen ? 'vsc' : ''}`} title="Toggle chat"><Icon name="MessageSquare" size={16} /></button>
        <button type="button" className="hdr-btn vsc"><Icon name="ExternalLink" size={14} className="gi" />VS Code</button>
        <div className="winbtns">
          <button type="button" className="winbtn"><Icon name="Minus" size={13} /></button>
          <button type="button" className="winbtn"><Icon name="Square" size={11} /></button>
          <button type="button" className="winbtn close"><Icon name="X" size={14} /></button>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {runBar && <RunBar blocked={blocked} />}
        <div className="body" style={{ flex: 1, minHeight: 0, gridTemplateColumns: chat ? 'var(--side-w) 1fr auto' : undefined }}>
          {sidebar}
          {children}
          {chat}
        </div>
      </div>
    </div>
  );
}

function SideSection({ children }) {
  return <div className="side-section">{children}</div>;
}
function TreeRow({ caret, icon, children, tag, active, navActive, color }) {
  return (
    <button type="button" className={`tree-row ${navActive ? 'nav active' : ''} ${active ? 'active' : ''}`}>
      {caret && <Icon name="ChevronRight" size={12} className="tw" />}
      {icon && <span className="tg" style={color ? { color } : undefined}><Icon name={icon} size={15} /></span>}
      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{children}</span>
      {tag && <span className="ttag">{tag}</span>}
    </button>
  );
}

function NotebookSidebar({ activeFile = 'pathly-build.md', showLocal = true }) {
  return (
    <div className="side">
      <div className="side-tabs">
        <button type="button" className="side-tab active">Files</button>
        <button type="button" className="side-tab">Library</button>
      </div>
      <div className="side-search">
        <input className="input search" placeholder="Filter files…" />
      </div>
      <div className="side-scroll">
        <SideSection>Skills</SideSection>
        <TreeRow icon="BookOpen" tag="md" navActive={activeFile === 'pathly-build.md'}>pathly-build.md</TreeRow>
        <TreeRow icon="BookOpen" tag="md">pathly-plan.md</TreeRow>
        <TreeRow icon="BookOpen" tag="md">pathly-review.md</TreeRow>
        <TreeRow icon="BookOpen" tag="md">pathly-test.md</TreeRow>
        {showLocal && <>
          <div className="side-section" style={{ color: 'var(--peach)' }}>Local · this project</div>
          <TreeRow icon="BookOpen" tag="local" color="var(--peach)">my-review-strict.md</TreeRow>
        </>}
        <SideSection>Agents</SideSection>
        <TreeRow icon="Bot">builder</TreeRow>
        <TreeRow icon="Bot">reviewer</TreeRow>
        <TreeRow icon="Bot">tester</TreeRow>
        <SideSection>Feature files</SideSection>
        <TreeRow icon="FileText">USER_STORIES.md</TreeRow>
        <TreeRow icon="FileText">REVIEW_FAILURES.md</TreeRow>
      </div>
      <div className="side-foot">
        <div className="avatar">P</div>
        <div className="who">
          <div className="nm">Pathly</div>
          <div className="em">local · :8765</div>
        </div>
      </div>
    </div>
  );
}

function MonitorSidebar({ active = 'skill-notebook-editor' }) {
  const feats = [
    { n: 'skill-notebook-editor', s: 'building', ico: 'CircleDot' },
    { n: 'auth-refactor', s: 'reviewing', ico: 'Circle' },
    { n: 'payments-v2', s: 'done', ico: 'CircleCheck' },
    { n: 'otel-exporter', s: 'done', ico: 'CircleCheck' },
  ];
  return (
    <div className="side">
      <div className="side-tabs">
        <button type="button" className="side-tab active">Workspace</button>
        <button type="button" className="side-tab">Library</button>
      </div>
      <div className="side-search">
        <input className="input search" placeholder="Filter features…" />
      </div>
      <div className="side-scroll">
        <SideSection>Features</SideSection>
        {feats.map(f => (
          <TreeRow key={f.n} icon={f.ico} active={f.n === active}
            color={f.s === 'building' ? 'var(--blue)' : f.s === 'reviewing' ? 'var(--peach)' : 'var(--green)'}>
            {f.n}
          </TreeRow>
        ))}
        <div style={{ height: 8 }}></div>
        <TreeRow icon="Activity" navActive>Monitor</TreeRow>
        <TreeRow icon="Database">DB Explorer</TreeRow>
        <TreeRow icon="Settings">Settings</TreeRow>
      </div>
      <div className="side-foot">
        <div className="avatar">P</div>
        <div className="who">
          <div className="nm">Pathly</div>
          <div className="em">local · :8765</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Icon, StudioShell, RunBar, SideSection, TreeRow, NotebookSidebar, MonitorSidebar, VIEWS });
