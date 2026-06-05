/* AgentsTab.jsx — cost bar chart (CSS bars) + invocations table */
const { fmtMoney, fmtNum, resultClass, shortTrace } = window.DBData;

const AGENT_COLOR = {
  builder: 'var(--blue)', reviewer: 'var(--peach)', tester: 'var(--mauve)',
};
const agentColor = (a) => AGENT_COLOR[a] || 'var(--sapphire)';

function AgentsTab({ agents }) {
  if (!agents.length) {
    return <div className="empty"><div className="ei">◷</div><div>No AGENT_DONE events for this feature yet.</div></div>;
  }
  const maxCost = Math.max(...agents.map(a => a.cost_usd));

  return (
    <div>
      {/* Section 1 — cost bar chart */}
      <div className="section-label">
        <h3>Cost per invocation</h3>
        <span className="hint">{agents.length} agents · {fmtMoney(agents.reduce((s,a)=>s+a.cost_usd,0))} total</span>
      </div>
      <div className="cost-chart">
        {agents.map((a, i) => (
          <div className="bar-row" key={i}>
            <span className="blabel">{a.agent} <span className="muted">(conv {a.conversation})</span></span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${Math.max(4, (a.cost_usd / maxCost) * 100)}%`, '--bar-c': agentColor(a.agent) }}></div>
            </div>
            <span className="bval">{fmtMoney(a.cost_usd)}</span>
            <div className="bar-tip">
              <b>{a.agent}</b> · conv {a.conversation} · {a.model}<br />
              <b>{fmtNum(a.total_tokens)}</b> tok · <b>{a.tool_uses}</b> tools · <b>{a.wall_seconds}s</b> · {a.result}
            </div>
          </div>
        ))}
      </div>

      {/* Section 2 — invocations table */}
      <div className="section-label">
        <h3>Agent invocations</h3>
        <span className="hint">AGENT_DONE event detail</span>
      </div>
      <div className="tbl-wrap">
        <table className="dbx">
          <thead>
            <tr>
              <th style={{ width: 34 }}>#</th>
              <th>Agent</th>
              <th style={{ width: 50 }}>Conv</th>
              <th>Model</th>
              <th style={{ width: 84 }}>Tokens</th>
              <th style={{ width: 64 }}>Cost</th>
              <th style={{ width: 78 }}>Wall</th>
              <th style={{ width: 78 }}>Result</th>
              <th style={{ width: 96 }}>trace_id</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a, i) => (
              <tr key={i}>
                <td className="num muted">{i + 1}</td>
                <td className="mono" style={{ color: agentColor(a.agent) }}>{a.agent}</td>
                <td className="num">{a.conversation}</td>
                <td className="mono muted">{a.model}</td>
                <td className="num">{fmtNum(a.total_tokens)}</td>
                <td className="num" style={{ color: 'var(--green)' }}>{fmtMoney(a.cost_usd)}</td>
                <td className="num muted">{a.wall_seconds}s</td>
                <td>
                  <span className={`badge soft ${resultClass(a.result)}`}><span className="bd"></span>{a.result}</span>
                </td>
                <td className="mono">
                  {a.trace_id
                    ? <span title={a.trace_id}>{shortTrace(a.trace_id)}</span>
                    : <span className="muted">none</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.AgentsTab = AgentsTab;
