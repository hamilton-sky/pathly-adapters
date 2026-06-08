/* notebook-directions.jsx — 3 design directions for the Notebook surface.
   NotebookV1 (Evolved Colab), NotebookV2 (Document focus + import dialog),
   NotebookV3 (Split inspector). All render inside StudioShell. */

/* ---- rendered skill-cell bodies (pathly-build.md) ---- */
const CB = {
  h1: () => <div className="cell-render"><h1>pathly-build</h1><p>Skill contract for the <strong>builder</strong> agent during the BUILD stage.</p></div>,
  role: () => <div className="cell-render"><h2>Role</h2><p>You are the <strong>builder</strong>. Implement the plan in <code>IMPL_PLAN.md</code> one task at a time. Run tests after each change and keep the working tree green.</p></div>,
  loop: () => <div className="cell-render"><h3>implementation-loop <span className="badge" style={{ '--b-c': 'var(--green)' }}><span className="bd"></span>CORE</span></h3><p>For each task: write the failing test, implement, run the suite, then log progress mid-phase.</p></div>,
  log: () => <div className="cell-render"><h2>Mid-phase logging</h2><pre><code>curl -s :8765/log -d \'{"{"}phase":"BUILD",<br/>  "msg":"task 3/8 done"{"}"}\'</code></pre></div>,
  gate: () => <div className="cell-render"><h3>done-criteria <span className="badge" style={{ '--b-c': 'var(--yellow)' }}><span className="bd"></span>GATE</span></h3><p>All acceptance tests pass and no <code>TODO(builder)</code> markers remain.</p></div>,
};

function ToolbarBtns({ kebab }) {
  return (
    <div className="cell-toolbar" style={{ opacity: 1, transform: 'none', pointerEvents: 'auto' }}>
      <button type="button" className="ct-btn" title="Move up"><Icon name="ArrowUp" size={14} /></button>
      <button type="button" className="ct-btn" title="Move down"><Icon name="ArrowDown" size={14} /></button>
      <button type="button" className="ct-btn" title="Edit"><Icon name="Pencil" size={14} /></button>
      <button type="button" className="ct-btn" title="More" style={kebab ? { background: 'var(--surface0)', color: 'var(--text-primary)' } : undefined}><Icon name="MoreHorizontal" size={14} /></button>
      <button type="button" className="ct-btn danger" title="Delete"><Icon name="Trash2" size={14} /></button>
    </div>
  );
}

function MenuItem({ icon, children, kbd, chev, danger }) {
  return (
    <button type="button" className={danger ? 'danger' : ''}>
      <span className="mi"><Icon name={icon} size={14} /></span>{children}
      {kbd && <span className="kbd">{kbd}</span>}
      {chev && <Icon name="ChevronRight" size={13} className="chev" />}
    </button>
  );
}

function KebabMenu() {
  return (
    <div className="rd-menu">
      <MenuItem icon="Copy" kbd="⌘C">Copy cell</MenuItem>
      <MenuItem icon="Clipboard">Copy content as text</MenuItem>
      <MenuItem icon="CopyPlus">Duplicate</MenuItem>
      <MenuItem icon="Replace" chev>Change type</MenuItem>
      <MenuItem icon="Component">Make fragment</MenuItem>
      <hr />
      <MenuItem icon="Trash2" danger>Delete cell</MenuItem>
    </div>
  );
}

function NBCell({ kind, body, num, selected, toolbar, kebab, selBubble }) {
  return (
    <div className={`cell kind-${kind} ${selected ? 'selected' : ''}`} style={{ position: 'relative' }}>
      <span className="cell-num">[{num}]</span>
      {toolbar && <ToolbarBtns kebab={kebab} />}
      {kebab && <KebabMenu />}
      <div className="cell-body">{body}</div>
      {selBubble && (
        <div className="rd-selbubble" style={{ left: 150, top: 64 }}><Icon name="Scissors" size={13} /> New cell from selection</div>
      )}
    </div>
  );
}

function NBTopBar({ crumb = ['Skills', 'pathly-build'] }) {
  return (
    <div className="nb-bar">
      <div className="nb-crumb">
        {crumb.map((seg, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="sl">›</span>}
            <span className={`seg ${i === crumb.length - 1 ? 'last' : ''}`}>{seg}</span>
          </React.Fragment>
        ))}
        <span className="nbbadge">NOTEBOOK</span>
      </div>
      <span className="sp"></span>
      <button type="button" className="nb-tool" title="Undo"><Icon name="Undo2" size={15} /></button>
      <button type="button" className="nb-tool" title="Redo"><Icon name="Redo2" size={15} /></button>
      <button type="button" className="btn sm" style={{ marginLeft: 4 }}>Validate</button>
      <button type="button" className="publish" style={{ height: 28 }}>Export Skill</button>
    </div>
  );
}

function ComposedPreview({ raw }) {
  return (
    <div className="nb-right">
      <div className="nb-prev-bar">
        <input className="input fp" placeholder="Feature path…" defaultValue="auth-service / login-flow" />
        <div className="nb-prev-toggle">
          <button type="button" className={raw ? '' : 'active'}>Preview</button>
          <button type="button" className={raw ? 'active' : ''}>Raw</button>
        </div>
      </div>
      <div className="nb-prev-body">
        <span className="prev-badge">COMPOSED SKILL · 5 CELLS</span>
        <div style={{ height: 14 }}></div>
        {raw ? (
          <div className="nb-prev-raw">{`# pathly-build

Skill contract for the builder agent during the BUILD stage.

## Role
You are the builder. Implement the plan in IMPL_PLAN.md one task at a time…

### implementation-loop \`CORE\`
For each task: write the failing test, implement, run the suite…

## Mid-phase logging
curl -s :8765/log -d '{"phase":"BUILD","msg":"task 3/8 done"}'

### done-criteria \`GATE\`
All acceptance tests pass and no TODO(builder) markers remain.`}</div>
        ) : (
          <div className="cell-render">
            <h1>pathly-build</h1>
            <p>Skill contract for the <strong>builder</strong> agent during the BUILD stage.</p>
            <h2>Role</h2>
            <p>You are the <strong>builder</strong>. Implement the plan in <code>IMPL_PLAN.md</code> one task at a time. Run tests after each change.</p>
            <h3>implementation-loop</h3>
            <p>For each task: write the failing test, implement, run the suite, then log progress.</p>
            <h2>Mid-phase logging</h2>
            <pre><code>curl -s :8765/log -d '...'</code></pre>
            <h3>done-criteria</h3>
            <p>All acceptance tests pass and no <code>TODO(builder)</code> markers remain.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============ V1 — Evolved Colab (two-pane, all affordances) ============ */
function NotebookV1() {
  return (
    <StudioShell view="notebook" sidebar={<NotebookSidebar />}>
      <div className="main">
        <div className="nb">
          <div className="nb-left">
            <NBTopBar />
            <div className="nb-search">
              <input className="input search" placeholder="Search the skill text…" />
              <span className="meta">5 cells</span>
            </div>
            <div className="nb-cells">
              <NBCell kind="heading" num={1} body={<CB.h1 />} />
              <NBCell kind="markdown" num={2} body={<CB.role />} selected toolbar selBubble />
              <NBCell kind="fragment" num={3} body={<CB.loop />} kebab toolbar />
              <NBCell kind="markdown" num={4} body={<CB.log />} />
              <NBCell kind="fragment" num={5} body={<CB.gate />} />
              <div className="nb-add">
                <button type="button" className="btn sm"><Icon name="Plus" size={13} />Text cell</button>
                <button type="button" className="btn sm"><Icon name="Component" size={13} />Fragment</button>
                <button type="button" className="btn sm"><Icon name="FileInput" size={13} />Import .md</button>
              </div>
            </div>
          </div>
          <ComposedPreview />
        </div>
      </div>
    </StudioShell>
  );
}

/* ============ V2 — Document focus + import dialog ============ */
function NotebookV2() {
  return (
    <StudioShell view="notebook" sidebar={<NotebookSidebar />}>
      <div className="main" style={{ position: 'relative' }}>
        <NBTopBar />
        <div className="rd-doc">
          <div className="rd-doc-col">
            <div style={{ position: 'relative' }}><span className="rd-gutter-num">[1]</span>
              <NBCell kind="heading" num={1} body={<CB.h1 />} /></div>
            <div style={{ position: 'relative' }}><span className="rd-gutter-num">[2]</span>
              <NBCell kind="markdown" num={2} body={<CB.role />} selected toolbar /></div>
            <div style={{ position: 'relative' }}><span className="rd-gutter-num">[3]</span>
              <NBCell kind="fragment" num={3} body={<CB.loop />} /></div>
          </div>
          <div className="rd-slideover-tab"><span className="pv-dot"></span>Composed preview ‹</div>
        </div>

        {/* Import .md split-confirm dialog (overlay) */}
        <div className="scrim" style={{ position: 'absolute' }}>
          <div className="rd-dialog">
            <div className="rd-dialog-head">
              <h3>Add markdown as cells</h3>
              <div className="sub">Dropped <code>REVIEW_FAILURES.md</code> — here's how Pathly will split it. Confirm, or insert as a single cell.</div>
            </div>
            <div className="rd-dialog-body">
              <div className="rd-dialog-pane">
                <div className="pl">Source file</div>
                <div className="rd-raw">{`# Review failures

## Blocking
- auth token not refreshed on 401

## Non-blocking
- rename ambiguous var \`x\``}</div>
              </div>
              <div className="rd-dialog-pane">
                <div className="pl">Proposed cells <span className="ttag" style={{ color: 'var(--green)' }}>3 cells</span></div>
                <div className="rd-splitcell h"><div className="sc-kind">Heading</div><div className="sc-title"># Review failures</div></div>
                <div className="rd-splitcell"><div className="sc-kind">Markdown</div><div className="sc-title">## Blocking</div><div className="sc-prev">auth token not refreshed on 401</div></div>
                <div className="rd-splitcell"><div className="sc-kind">Markdown</div><div className="sc-title">## Non-blocking</div><div className="sc-prev">rename ambiguous var x</div></div>
              </div>
            </div>
            <div className="rd-dialog-foot">
              <button type="button" className="btn">Insert as one cell</button>
              <span className="sp"></span>
              <button type="button" className="btn ghost">Cancel</button>
              <button type="button" className="publish" style={{ height: 32 }}>Confirm split · 3 cells</button>
            </div>
          </div>
        </div>
      </div>
    </StudioShell>
  );
}

/* ============ V3 — Split inspector ============ */
function InspectorPanel() {
  const [tab, setTab] = React.useState('preview');
  return (
    <div className="rd-insp">
      <div className="rd-insp-tabs">
        <button type="button" className={`rd-insp-tab ${tab === 'preview' ? 'active' : ''}`} onClick={() => setTab('preview')}>Preview</button>
        <button type="button" className={`rd-insp-tab ${tab === 'cell' ? 'active' : ''}`} onClick={() => setTab('cell')}>Cell</button>
        <button type="button" className={`rd-insp-tab ${tab === 'diff' ? 'active' : ''}`} onClick={() => setTab('diff')}>Override</button>
      </div>
      <div className="rd-insp-body">
        {tab === 'preview' && (
          <>
            <span className="prev-badge">COMPOSED · 5 CELLS</span>
            <div style={{ height: 12 }}></div>
            <div className="cell-render">
              <h1>pathly-build</h1>
              <h2>Role</h2>
              <p>You are the <strong>builder</strong>. Implement the plan one task at a time.</p>
              <h3>implementation-loop</h3>
              <p>Write the failing test, implement, run the suite.</p>
            </div>
          </>
        )}
        {tab === 'cell' && (
          <>
            <div className="rd-field"><div className="fl">Cell type</div>
              <div className="rd-select">Fragment <span style={{ color: 'var(--text-faint)' }}>▾</span></div></div>
            <div className="rd-field"><div className="fl">Fragment name</div>
              <div className="rd-select" style={{ fontFamily: 'var(--mono)' }}>implementation-loop</div></div>
            <div className="rd-field"><div className="fl">Badge</div>
              <div className="rd-chiprow">
                <span className="rd-chip on">CORE</span><span className="rd-chip">GATE</span><span className="rd-chip">OPT</span>
              </div></div>
            <div className="rd-field"><div className="fl">Compatible stages</div>
              <div className="rd-chiprow">
                <span className="rd-chip on">BUILD</span><span className="rd-chip">REVIEW</span><span className="rd-chip">TEST</span><span className="rd-chip">PLAN</span>
              </div></div>
          </>
        )}
        {tab === 'diff' && (
          <>
            <div className="section-label" style={{ marginBottom: 12 }}>
              <h3 style={{ fontSize: 12.5 }}>Local override</h3>
              <span className="hint">my-review-strict.md vs global</span>
            </div>
            <div className="rd-diff">
              <div className="dl ctx">  ## done-criteria `GATE`</div>
              <div className="dl del">- All acceptance tests pass.</div>
              <div className="dl add">+ All acceptance tests pass AND</div>
              <div className="dl add">+ coverage ≥ 90% on changed files.</div>
              <div className="dl ctx">  No TODO(builder) markers remain.</div>
            </div>
            <div style={{ marginTop: 14 }}>
              <button type="button" className="btn sm">Revert to global</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function NotebookV3() {
  return (
    <StudioShell view="notebook" sidebar={<NotebookSidebar />}>
      <div className="main">
        <div className="nb" style={{ gridTemplateColumns: '1.35fr 1fr' }}>
          <div className="nb-left">
            <NBTopBar crumb={['Skills', 'Local', 'my-review-strict']} />
            <div className="nb-search">
              <input className="input search" placeholder="Search the skill text…" />
              <span className="meta">5 cells · LOCAL</span>
            </div>
            <div className="nb-cells">
              <NBCell kind="heading" num={1} body={<CB.h1 />} />
              <NBCell kind="markdown" num={2} body={<CB.role />} />
              <NBCell kind="fragment" num={3} body={<CB.loop />} selected toolbar />
              <NBCell kind="fragment" num={4} body={<CB.gate />} />
            </div>
          </div>
          <InspectorPanel />
        </div>
      </div>
    </StudioShell>
  );
}

Object.assign(window, { NotebookV1, NotebookV2, NotebookV3 });
