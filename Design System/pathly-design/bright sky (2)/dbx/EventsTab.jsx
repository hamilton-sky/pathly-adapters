/* EventsTab.jsx — filterable event table with inline JSON expand + load more */
const { typeClass, fmtTime } = window.DBData;

/* JSON syntax highlighter — no external lib, regex spans */
function highlightJson(obj) {
  const json = JSON.stringify(obj, null, 2);
  const esc = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const html = esc.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g,
    (m) => {
      let cls = 'j-num';
      if (/^"/.test(m)) cls = /:$/.test(m) ? 'j-key' : 'j-str';
      else if (/true|false/.test(m)) cls = 'j-bool';
      else if (/null/.test(m)) cls = 'j-null';
      return `<span class="${cls}">${m}</span>`;
    }
  );
  return html;
}

function summaryText(payload) {
  const s = payload && (payload.summary || payload.reason);
  const text = s != null ? String(s) : JSON.stringify(payload);
  return text.length > 80 ? text.slice(0, 80) + '…' : text;
}

const PAGE = 100;

function EventsTab({ events }) {
  const [filter, setFilter] = React.useState('');
  const [limit, setLimit] = React.useState(PAGE);
  const [open, setOpen] = React.useState(null);

  const filtered = React.useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return events;
    return events.filter(e =>
      e.type.toLowerCase().includes(q) ||
      JSON.stringify(e.payload).toLowerCase().includes(q)
    );
  }, [events, filter]);

  const shown = filtered.slice(0, limit);

  React.useEffect(() => { setLimit(PAGE); setOpen(null); }, [filter]);

  return (
    <div>
      <div className="filter-bar">
        <input
          type="text" className="input search" placeholder="Filter by type or payload…"
          value={filter} onChange={e => setFilter(e.target.value)}
        />
        <span className="filter-meta">{filtered.length} / {events.length} events</span>
      </div>

      <div className="tbl-wrap">
        <table className="dbx">
          <thead>
            <tr>
              <th style={{ width: 56 }}>seq</th>
              <th style={{ width: 150 }}>type</th>
              <th style={{ width: 88 }}>ts</th>
              <th>summary</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(e => (
              <React.Fragment key={e.seq}>
                <tr
                  className={`clickable ${open === e.seq ? 'expanded' : ''}`}
                  onClick={() => setOpen(open === e.seq ? null : e.seq)}
                >
                  <td className="num muted">{e.seq}</td>
                  <td>
                    <span className={`badge ${typeClass(e.type)}`}>
                      <span className="bd"></span>{e.type}
                    </span>
                  </td>
                  <td className="mono muted">{fmtTime(e.ts)}</td>
                  <td className="cell-summary">{summaryText(e.payload)}</td>
                </tr>
                {open === e.seq && (
                  <tr className="json-row">
                    <td colSpan={4}>
                      <div className="json-box">
                        <pre className="json" dangerouslySetInnerHTML={{ __html: highlightJson(e.payload) }} />
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={4}><div className="empty" style={{ minHeight: 120 }}><div className="ei">⌕</div><div>No events match “{filter}”.</div></div></td></tr>
            )}
          </tbody>
        </table>
      </div>

      {limit < filtered.length && (
        <div className="load-more">
          <button type="button" className="btn sm" onClick={() => setLimit(l => l + PAGE)}>
            Load more ({filtered.length - limit} remaining)
          </button>
        </div>
      )}
    </div>
  );
}

window.EventsTab = EventsTab;
