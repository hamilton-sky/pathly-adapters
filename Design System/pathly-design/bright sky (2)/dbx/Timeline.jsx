/* Timeline.jsx — horizontal FSM state-transition strip */
const { stageClass, stageVar, fmtTime } = window.DBData;

function Timeline({ events }) {
  const transitions = React.useMemo(
    () => events.filter(e => e.type === 'STATE_TRANSITION')
      .slice().sort((a, b) => a.seq - b.seq)
      .map(e => ({ state: e.payload.to, ts: e.ts, reason: e.payload.reason })),
    [events]
  );

  if (!transitions.length) {
    return <div className="empty"><div className="ei">◇</div><div>No state transitions recorded yet.</div></div>;
  }

  // durations between transitions
  const dur = (i) => {
    if (i >= transitions.length - 1) return null;
    const a = new Date(transitions[i].ts).getTime();
    const b = new Date(transitions[i + 1].ts).getTime();
    const s = Math.round((b - a) / 1000);
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  const legendStates = ['BUILDING', 'REVIEWING', 'TESTING', 'RETRO', 'DONE', 'PLANNING'];

  return (
    <div>
      <p className="tab-title">State machine · {transitions.length} transitions</p>
      <div className="tl-scroll">
        <div className="tl-track">
          {transitions.map((t, i) => (
            <React.Fragment key={i}>
              <div className="tl-node">
                <div className={`tl-pill ${stageClass(t.state)}`} style={{ '--tl-c': stageVar(t.state) }} title={t.reason || ''}>
                  {t.state}
                </div>
                <div className="tl-ts">{fmtTime(t.ts)}</div>
                {dur(i) && <div className="tl-dur">↳ {dur(i)}</div>}
              </div>
              {i < transitions.length - 1 && <div className="tl-arrow">→</div>}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="tl-legend">
        {legendStates.map(s => (
          <div className="tl-leg" key={s}>
            <span className="sw" style={{ background: stageVar(s) }}></span>{s}
          </div>
        ))}
      </div>
    </div>
  );
}

window.Timeline = Timeline;
