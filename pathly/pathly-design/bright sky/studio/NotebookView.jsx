/* NotebookView.jsx — Colab-style skill cells (arrow reorder, no drag) +
   live markdown preview rail + search/highlight */
const { renderMarkdown } = window.MD;
const SKILL = window.StudioData.SKILL;

function Cell({ cell, index, total, selected, onSelect, search,
                onMove, onDelete, onEdit, editing, onSave, onCancel, moving }) {
  const [draft, setDraft] = React.useState(cell.md);
  const [expanded, setExpanded] = React.useState(false);
  React.useEffect(() => { setDraft(cell.md); }, [cell.md, editing]);

  const html = renderMarkdown(cell.md, search);
  const long = cell.md.length > 220;

  return (
    <div
      className={`cell kind-${cell.kind} ${selected ? 'selected' : ''} ${moving ? 'moving' : ''}`}
      onClick={() => onSelect(cell.id)}
    >
      <span className="cell-num">[{index + 1}]</span>

      <div className="cell-toolbar" onClick={e => e.stopPropagation()}>
        <button type="button" className="ct-btn" title="Move up" disabled={index === 0} onClick={() => onMove(index, -1)}>↑</button>
        <button type="button" className="ct-btn" title="Move down" disabled={index === total - 1} onClick={() => onMove(index, 1)}>↓</button>
        <button type="button" className="ct-btn" title={editing ? 'Editing' : 'Edit'} onClick={() => onEdit(cell.id)}>✎</button>
        <button type="button" className="ct-btn danger" title="Delete" onClick={() => onDelete(cell.id)}>🗑</button>
        <button type="button" className="ct-btn" title="More">⋮</button>
      </div>

      {editing ? (
        <div className="cell-edit" onClick={e => e.stopPropagation()}>
          <textarea value={draft} onChange={e => setDraft(e.target.value)} spellCheck={false} autoFocus />
          <div className="cell-edit-bar">
            <button type="button" className="btn primary sm" onClick={() => onSave(cell.id, draft)}>Save</button>
            <button type="button" className="btn ghost sm" onClick={onCancel}>Cancel</button>
          </div>
        </div>
      ) : (
        <React.Fragment>
          <div className="cell-body">
            <div
              className={`cell-render ${long && !expanded ? 'cell-collapsed' : ''}`}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          </div>
          {long && (
            <button type="button" className="showfull" onClick={e => { e.stopPropagation(); setExpanded(x => !x); }}>
              {expanded ? 'Show less' : 'Show full content'}
            </button>
          )}
          {cell.kind === 'fragment' && (
            <div className="cell-meta">
              <span className="cell-frag-title">{cell.title}</span>
              <span className="cell-frag-sub">— {cell.subtitle}</span>
              <span style={{ flex: 1 }}></span>
              {cell.badge && <span className="badge" style={{ '--b-c': 'var(--green)' }}><span className="bd"></span>{cell.badge}</span>}
            </div>
          )}
        </React.Fragment>
      )}
    </div>
  );
}

function NotebookView() {
  const [cells, setCells] = React.useState(SKILL.cells);
  const [selected, setSelected] = React.useState(SKILL.cells[0].id);
  const [editing, setEditing] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [moving, setMoving] = React.useState(null);
  const [previewMode, setPreviewMode] = React.useState('rendered');
  const [featurePath, setFeaturePath] = React.useState('');
  const [history, setHistory] = React.useState([]);

  const pushHistory = (prev) => setHistory(h => [...h, prev].slice(-30));
  const undo = () => setHistory(h => { if (!h.length) return h; setCells(h[h.length - 1]); return h.slice(0, -1); });

  const move = (index, dir) => {
    const j = index + dir;
    if (j < 0 || j >= cells.length) return;
    pushHistory(cells);
    const next = cells.slice();
    [next[index], next[j]] = [next[j], next[index]];
    setCells(next);
    setSelected(next[j].id);
    setMoving(next[j].id);
    setTimeout(() => setMoving(null), 280);
  };
  const del = (id) => { pushHistory(cells); setCells(cs => cs.filter(c => c.id !== id)); if (editing === id) setEditing(null); };
  const save = (id, md) => { pushHistory(cells); setCells(cs => cs.map(c => c.id === id ? { ...c, md } : c)); setEditing(null); };
  const addCell = (kind) => {
    pushHistory(cells);
    const id = 'c' + Math.random().toString(36).slice(2, 7);
    const md = kind === 'heading' ? '# New section' : kind === 'fragment' ? '### new-fragment `CORE`\n\nDescribe the fragment.' : '## New cell\n\nWrite **Markdown** here.';
    const cell = { id, kind, title: 'new', subtitle: 'new fragment', badge: kind === 'fragment' ? 'CORE' : undefined, md };
    setCells(cs => [...cs, cell]);
    setSelected(id); setEditing(id);
  };

  // search-filtered view (keeps all if empty)
  const q = search.trim().toLowerCase();
  const visible = q ? cells.filter(c => c.md.toLowerCase().includes(q)) : cells;
  const matchCount = q ? cells.filter(c => c.md.toLowerCase().includes(q)).length : null;

  // composed preview = all cells in order
  const composed = cells.map(c => c.md).join('\n\n');
  const previewHtml = renderMarkdown(composed, search);

  return (
    <div className="main">
      <div className="nb">
        {/* LEFT: cells */}
        <div className="nb-left">
          <div className="nb-bar">
            <div className="nb-crumb">
              {SKILL.breadcrumb.map((seg, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span className="sl">›</span>}
                  <span className={`seg ${i === SKILL.breadcrumb.length - 1 ? 'last' : ''}`}>{seg}</span>
                </React.Fragment>
              ))}
              <span className="nbbadge">NOTEBOOK</span>
            </div>
            <span className="sp"></span>
            <button type="button" className="nb-tool" title="Undo" onClick={undo} disabled={!history.length}>↶</button>
            <button type="button" className="nb-tool" title="Redo" disabled>↷</button>
            <button type="button" className="btn sm" style={{ marginLeft: 4 }}>Validate</button>
            <button type="button" className="publish" style={{ height: 28 }}>Export Skill</button>
          </div>

          <div className="nb-search">
            <input className="input search" placeholder="Search the skill text…" value={search} onChange={e => setSearch(e.target.value)} />
            {q && <span className="meta">{matchCount} cell{matchCount === 1 ? '' : 's'} match</span>}
          </div>

          <div className="nb-cells">
            {visible.map((cell) => {
              const realIndex = cells.findIndex(c => c.id === cell.id);
              return (
                <Cell
                  key={cell.id}
                  cell={cell}
                  index={realIndex}
                  total={cells.length}
                  selected={selected === cell.id}
                  onSelect={setSelected}
                  search={search}
                  onMove={move}
                  onDelete={del}
                  onEdit={(id) => setEditing(e => e === id ? null : id)}
                  editing={editing === cell.id}
                  onSave={save}
                  onCancel={() => setEditing(null)}
                  moving={moving === cell.id}
                />
              );
            })}
            {q && visible.length === 0 && (
              <div className="empty" style={{ minHeight: 160 }}><div className="ei">⌕</div><div>No cells contain “{search}”.</div></div>
            )}
            {!q && (
              <div className="nb-add">
                <button type="button" className="btn sm" onClick={() => addCell('markdown')}>+ Text cell</button>
                <button type="button" className="btn sm" onClick={() => addCell('fragment')}>+ Fragment</button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: live preview */}
        <div className="nb-right">
          <div className="nb-prev-bar">
            <input className="input fp" placeholder="Feature path…" value={featurePath} onChange={e => setFeaturePath(e.target.value)} />
            <div className="nb-prev-toggle">
              <button type="button" className={previewMode === 'rendered' ? 'active' : ''} onClick={() => setPreviewMode('rendered')}>Preview</button>
              <button type="button" className={previewMode === 'raw' ? 'active' : ''} onClick={() => setPreviewMode('raw')}>Raw</button>
            </div>
          </div>
          <div className="nb-prev-body">
            <span className="prev-badge">COMPOSED SKILL · {cells.length} CELLS</span>
            <div style={{ height: 14 }}></div>
            {previewMode === 'rendered'
              ? <div className="cell-render" dangerouslySetInnerHTML={{ __html: previewHtml }} />
              : <div className="nb-prev-raw">{composed}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

window.NotebookView = NotebookView;
