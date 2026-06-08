/* SqlTab.jsx — SELECT query box, sortable results, copy CSV */
const { runSql } = window.DBData;

const DEFAULT_SQL = 'SELECT feature, type, ts FROM fsm_events ORDER BY seq DESC LIMIT 20';

function SqlTab({ pushToast }) {
  const [sql, setSql] = React.useState(DEFAULT_SQL);
  const [result, setResult] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [sort, setSort] = React.useState({ col: null, dir: 1 });

  const run = () => {
    const r = runSql(sql);
    if (r.error) { setError(r.error); setResult(null); return; }
    setError(null);
    setSort({ col: null, dir: 1 });
    setResult(r);
  };

  React.useEffect(() => { run(); }, []); // run prefilled query on mount

  const sortedRows = React.useMemo(() => {
    if (!result) return [];
    if (sort.col === null) return result.rows;
    const ci = sort.col;
    return result.rows.slice().sort((a, b) => {
      const x = a[ci], y = b[ci];
      const nx = Number(x), ny = Number(y);
      const numeric = !isNaN(nx) && !isNaN(ny) && x !== '' && y !== '';
      if (numeric) return (nx - ny) * sort.dir;
      return String(x).localeCompare(String(y)) * sort.dir;
    });
  }, [result, sort]);

  const toggleSort = (ci) => {
    setSort(s => s.col === ci ? { col: ci, dir: -s.dir } : { col: ci, dir: 1 });
  };

  const copyCsv = () => {
    if (!result) return;
    const esc = (v) => {
      const s = String(v ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [result.columns.map(esc).join(',')];
    sortedRows.forEach(r => lines.push(r.map(esc).join(',')));
    const csv = lines.join('\n');
    navigator.clipboard?.writeText(csv).then(
      () => pushToast({ kind: 'green', title: 'Copied to clipboard', msg: `${sortedRows.length} rows as CSV` }),
      () => pushToast({ kind: 'red', title: 'Copy failed', msg: 'Clipboard unavailable' })
    );
  };

  return (
    <div>
      <textarea
        className="sql-editor" rows={6} spellCheck={false}
        value={sql} onChange={e => setSql(e.target.value)}
        onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') run(); }}
      />
      <div className="sql-bar">
        <button type="button" className="btn primary" onClick={run}>
          <span className="gi">▷</span> Run <span className="muted" style={{ fontSize: 11 }}>⌘↵</span>
        </button>
        <button type="button" className="btn" onClick={copyCsv} disabled={!result || !result.rows.length}>
          <span className="gi">⧉</span> Copy CSV
        </button>
        <button type="button" className="btn ghost" onClick={() => setSql(DEFAULT_SQL)}>Reset</button>
        <span className="sql-note"><span className="lock">🔒</span> Only SELECT queries are allowed.</span>
      </div>

      {error && <div className="sql-err">⚠ {error}</div>}

      {result && (
        <div>
          <div className="sql-result-meta">{sortedRows.length} rows · {result.columns.length} columns · click a header to sort</div>
          <div className="tbl-wrap">
            <table className="dbx">
              <thead>
                <tr>
                  {result.columns.map((c, ci) => (
                    <th key={ci} className="sortable" onClick={() => toggleSort(ci)}>
                      {c}{sort.col === ci && <span className="sort-i">{sort.dir > 0 ? '▲' : '▼'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci} className={typeof cell === 'number' || /^\d+$/.test(String(cell)) ? 'num mono' : 'mono'} style={{ color: ci === 0 ? 'var(--text-secondary)' : undefined }}>
                        {cell === null ? <span className="muted">NULL</span> : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
                {sortedRows.length === 0 && (
                  <tr><td colSpan={result.columns.length}><div className="empty" style={{ minHeight: 100 }}><div className="ei">∅</div><div>Query returned no rows.</div></div></td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

window.SqlTab = SqlTab;
