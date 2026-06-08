/* ============================================================
   data.jsx — deterministic mock FSM pipeline dataset
   Mirrors GET /db/features, /db/features/<name>/events, /state
   ============================================================ */

const BASE = '2026-06-05T';
const iso = (h, m, s) => `${BASE}${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}Z`;

const STAGE_CLASS = {
  BUILDING: 'st-building', REVIEWING: 'st-reviewing', TESTING: 'st-testing',
  RETRO: 'st-retro', DONE: 'st-done', PLANNING: 'st-planning',
};
const stageClass = (s) => STAGE_CLASS[s] || 'st-other';
const STAGE_VAR = {
  BUILDING: 'var(--blue)', REVIEWING: 'var(--peach)', TESTING: 'var(--mauve)',
  RETRO: 'var(--teal)', DONE: 'var(--green)', PLANNING: 'var(--overlay1)',
};
const stageVar = (s) => STAGE_VAR[s] || 'var(--surface2)';

const typeClass = (t) => 'ev-' + String(t || '').toLowerCase();
const resultClass = (r) => {
  const v = String(r || '').toLowerCase();
  if (v === 'pass' || v === 'done' || v === 'ok') return 'rs-pass';
  if (v === 'fail' || v === 'error') return 'rs-fail';
  return 'rs-unknown';
};

const fmtMoney = (n) => '$' + Number(n).toFixed(2);
const fmtNum = (n) => Number(n).toLocaleString('en-US');
const fmtTime = (isoStr) => (isoStr || '').slice(11, 19);
const shortTrace = (t) => (t ? String(t).slice(0, 8) : null);

/* ---- hand-authored agent invocations for fsm-sqlite (8 AGENT_DONE) ---- */
const FSM_AGENTS = [
  { agent: 'builder',  conversation: 1, model: 'claude-sonnet-4', tokens_in: 41200, tokens_out: 7010, total_tokens: 48210, cost_usd: 0.39, wall_seconds: 86.4, tool_uses: 14, result: 'pass', summary: 'Implemented migrate_to_sqlite.py schema + event writer; created fsm_events table.', trace_id: '9f3a2b1c4d5e6f70', span_id: 'a1b2c3d4' },
  { agent: 'reviewer', conversation: 1, model: 'claude-opus-4',   tokens_in: 27800, tokens_out: 3744, total_tokens: 31544, cost_usd: 0.71, wall_seconds: 52.1, tool_uses: 6,  result: 'pass', summary: 'Reviewed schema. Flagged missing index on seq; otherwise approved.', trace_id: '7c8d9e0f1a2b3c40', span_id: 'b2c3d4e5' },
  { agent: 'builder',  conversation: 2, model: 'claude-sonnet-4', tokens_in: 44980, tokens_out: 7920, total_tokens: 52900, cost_usd: 0.42, wall_seconds: 94.7, tool_uses: 18, result: 'pass', summary: 'Added composite index (feature, seq); implemented attach-all query path.', trace_id: '2b3c4d5e6f708192', span_id: 'c3d4e5f6' },
  { agent: 'tester',   conversation: 2, model: 'claude-sonnet-4', tokens_in: 25100, tokens_out: 3660, total_tokens: 28760, cost_usd: 0.23, wall_seconds: 61.0, tool_uses: 9,  result: 'fail', summary: '3/12 query tests failing: NULL ts breaks ORDER BY ts DESC ordering.', trace_id: 'd4e5f6a7b8c9d0e1', span_id: 'd4e5f6a7' },
  { agent: 'reviewer', conversation: 2, model: 'claude-opus-4',   tokens_in: 29400, tokens_out: 3612, total_tokens: 33012, cost_usd: 0.74, wall_seconds: 49.8, tool_uses: 5,  result: 'pass', summary: 'Approved with note: coalesce NULL ts before ordering.', trace_id: 'e5f6a7b8c9d0e1f2', span_id: 'e5f6a7b8' },
  { agent: 'builder',  conversation: 3, model: 'claude-sonnet-4', tokens_in: 34200, tokens_out: 5915, total_tokens: 40115, cost_usd: 0.33, wall_seconds: 77.2, tool_uses: 12, result: 'pass', summary: 'COALESCE(ts, created_at) in ordering; fixed NULL handling end-to-end.', trace_id: 'f6a7b8c9d0e1f203', span_id: 'f6a7b8c9' },
  { agent: 'tester',   conversation: 3, model: 'claude-sonnet-4', tokens_in: 26450, tokens_out: 3760, total_tokens: 30210, cost_usd: 0.24, wall_seconds: 58.3, tool_uses: 10, result: 'pass', summary: '12/12 query tests passing. Migration verified against 3 feature DBs.', trace_id: 'a7b8c9d0e1f20314', span_id: 'a7b8c9d0' },
  { agent: 'reviewer', conversation: 3, model: 'claude-opus-4',   tokens_in: 23010, tokens_out: 2988, total_tokens: 25998, cost_usd: 0.58, wall_seconds: 41.5, tool_uses: 4,  result: 'done', summary: 'Final approval. Schema + migration ready; transitioning to RETRO.', trace_id: null, span_id: null },
];

/* ---- fsm-sqlite state timeline ---- */
const FSM_TRANSITIONS = [
  { state: 'PLANNING',  ts: iso(9, 2, 11) },
  { state: 'BUILDING',  ts: iso(9, 8, 40) },
  { state: 'REVIEWING', ts: iso(9, 21, 6) },
  { state: 'TESTING',   ts: iso(9, 27, 33) },
  { state: 'BUILDING',  ts: iso(9, 34, 18) },
  { state: 'REVIEWING', ts: iso(9, 46, 2) },
  { state: 'TESTING',   ts: iso(9, 52, 49) },
  { state: 'RETRO',     ts: iso(10, 1, 27) },
  { state: 'DONE',      ts: iso(10, 6, 5) },
];

/* ---- build a full interleaved event log for fsm-sqlite ---- */
function buildFsmEvents() {
  const ev = [];
  let seq = 0;
  const push = (type, ts, payload) => ev.push({ seq: ++seq, type, ts, payload });

  push('STATE_TRANSITION', FSM_TRANSITIONS[0].ts, { from: null, to: 'PLANNING', reason: 'feature created' });
  push('PHASE_START', iso(9, 2, 30), { phase: 'planning', feature: 'fsm-sqlite' });
  push('PHASE_DONE', iso(9, 8, 12), { phase: 'planning', plan_steps: 6, duration_s: 342 });

  const convOrder = [
    { idx: 0, t: FSM_TRANSITIONS[1] }, // BUILDING
    { idx: 1, t: FSM_TRANSITIONS[2] }, // REVIEWING
    { idx: 2, t: FSM_TRANSITIONS[3], gate: 'fail' }, // TESTING -> tester fail
    { idx: 3, t: FSM_TRANSITIONS[4] }, // BUILDING (rework)
    { idx: 4, t: FSM_TRANSITIONS[5] }, // REVIEWING
    { idx: 5, t: FSM_TRANSITIONS[6] }, // TESTING
  ];

  let ah = 9, am = 9, as = 0;
  const bump = (mins) => { am += mins; while (am >= 60) { am -= 60; ah++; } };

  // map agents into phases
  const agentSeq = [0,1,2,3,4,5,6]; // first 7 across building/review/test loops
  let ai = 0;
  for (const phase of convOrder) {
    const tr = phase.t;
    push('STATE_TRANSITION', tr.ts, { from: ev.filter(e=>e.type==='STATE_TRANSITION').slice(-1)[0]?.payload.to || null, to: tr.state, reason: 'gate passed' });
    push('PHASE_START', tr.ts, { phase: tr.state.toLowerCase(), feature: 'fsm-sqlite' });
    const a = FSM_AGENTS[ai];
    if (a) {
      bump(2); as = (as + 23) % 60;
      push('AGENT_DONE', iso(ah, am, as), { ...a });
      ai++;
    }
    if (phase.gate === 'fail') {
      bump(1);
      push('GATE_FAILED', iso(ah, am, (as+9)%60), { gate: 'tests', reason: '3/12 failing: NULL ts ordering', conversation: a?.conversation });
    } else {
      bump(1);
      push('PHASE_DONE', iso(ah, am, (as+5)%60), { phase: tr.state.toLowerCase(), result: 'pass' });
    }
  }
  // a skipped gate during rework
  push('GATE_SKIPPED', iso(9, 49, 12), { gate: 'lint', reason: 'no source changes since last lint' });

  // final TESTING green pass — tester conv 3 (FSM_AGENTS[6])
  push('AGENT_DONE', iso(9, 55, 30), { ...FSM_AGENTS[6] });
  push('PHASE_DONE', iso(9, 56, 14), { phase: 'testing', result: 'pass', tests: '12/12' });

  // RETRO + final reviewer + DONE
  push('STATE_TRANSITION', FSM_TRANSITIONS[7].ts, { from: 'TESTING', to: 'RETRO', reason: 'all gates passed' });
  push('PHASE_START', FSM_TRANSITIONS[7].ts, { phase: 'retro', feature: 'fsm-sqlite' });
  push('AGENT_DONE', iso(10, 3, 40), { ...FSM_AGENTS[7] }); // reviewer conv3 = done
  push('PHASE_DONE', iso(10, 5, 2), { phase: 'retro', notes: 'schema stable; migration idempotent' });
  push('STATE_TRANSITION', FSM_TRANSITIONS[8].ts, { from: 'RETRO', to: 'DONE', reason: 'retro complete' });

  return ev.reverse(); // newest first
}

/* ---- generator for lighter features ---- */
function seeded(seed) { let s = seed; return () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff; }; }

function genEvents(feat) {
  const rnd = seeded(feat.seed);
  const ev = [];
  let seq = 0;
  const push = (type, ts, payload) => ev.push({ seq: ++seq, type, ts, payload });
  const agents = ['builder','reviewer','tester'];
  const models = ['claude-sonnet-4','claude-opus-4','claude-haiku-4'];
  let h = 8, m = 5;
  const path = feat.path;
  let prev = null;
  let conv = 1, ad = 0;
  for (let i = 0; i < path.length; i++) {
    const st = path[i];
    m += 4 + Math.floor(rnd()*6); while (m >= 60){ m-=60; h++; }
    push('STATE_TRANSITION', iso(h,m,Math.floor(rnd()*59)), { from: prev, to: st, reason: i===0?'feature created':'gate passed' });
    push('PHASE_START', iso(h,m,Math.floor(rnd()*59)), { phase: st.toLowerCase(), feature: feat.name });
    if ((st==='BUILDING'||st==='REVIEWING'||st==='TESTING') && ad < feat.agent_done_count) {
      const ag = st==='BUILDING'?'builder':st==='REVIEWING'?'reviewer':'tester';
      const tin = 18000 + Math.floor(rnd()*30000), tout = 2500 + Math.floor(rnd()*6000);
      const cost = +(0.18 + rnd()*0.6).toFixed(2);
      const fail = st==='TESTING' && rnd() < 0.25;
      m += 2; while (m>=60){m-=60;h++;}
      push('AGENT_DONE', iso(h,m,Math.floor(rnd()*59)), {
        agent: ag, conversation: conv, model: models[Math.floor(rnd()*models.length)],
        tokens_in: tin, tokens_out: tout, total_tokens: tin+tout, cost_usd: cost,
        wall_seconds: +(35+rnd()*70).toFixed(1), tool_uses: 3+Math.floor(rnd()*16),
        result: fail?'fail':(i===path.length-1&&ag==='reviewer'?'done':'pass'),
        summary: `${ag} pass on conversation ${conv} for ${feat.name}.`,
        trace_id: rnd()<0.85 ? Array.from({length:16},()=>'0123456789abcdef'[Math.floor(rnd()*16)]).join('') : null,
        span_id: rnd()<0.85 ? Array.from({length:8},()=>'0123456789abcdef'[Math.floor(rnd()*16)]).join('') : null,
      });
      ad++;
      if (fail) push('GATE_FAILED', iso(h,m,Math.floor(rnd()*59)), { gate:'tests', reason:'assertion failures', conversation: conv });
      else push('PHASE_DONE', iso(h,m,Math.floor(rnd()*59)), { phase: st.toLowerCase(), result:'pass' });
    }
    if (st==='TESTING') conv++;
    prev = st;
  }
  // pad to event_count with phase noise
  while (ev.length < feat.event_count) {
    m += 1; while (m>=60){m-=60;h++;}
    push(rnd()<0.5?'PHASE_START':'PHASE_DONE', iso(h,m,Math.floor(rnd()*59)), { phase:'misc', n: ev.length });
  }
  return ev.reverse();
}

/* ---- feature definitions ---- */
const FEATURE_DEFS = [
  { name:'fsm-sqlite', state:'DONE', convs_done:3, convs_total:3, event_count:35, agent_done_count:8, total_tokens:290749, total_cost_usd:3.64, last_event_ts: iso(10,6,5), path:['PLANNING','BUILDING','REVIEWING','TESTING','BUILDING','REVIEWING','TESTING','RETRO','DONE'], _rich:true },
  { name:'auth-refactor', state:'BUILDING', convs_done:1, convs_total:3, event_count:23, agent_done_count:4, total_tokens:142300, total_cost_usd:1.92, last_event_ts: iso(11,14,2), path:['PLANNING','BUILDING','REVIEWING','BUILDING'], seed:1337 },
  { name:'payments-webhook', state:'REVIEWING', convs_done:2, convs_total:2, event_count:31, agent_done_count:6, total_tokens:201450, total_cost_usd:2.74, last_event_ts: iso(11,38,55), path:['PLANNING','BUILDING','REVIEWING','TESTING','REVIEWING'], seed:4242 },
  { name:'search-index', state:'TESTING', convs_done:1, convs_total:2, event_count:18, agent_done_count:3, total_tokens:98700, total_cost_usd:1.21, last_event_ts: iso(10,52,9), path:['PLANNING','BUILDING','TESTING'], seed:8888 },
  { name:'onboarding-flow', state:'DONE', convs_done:3, convs_total:3, event_count:52, agent_done_count:9, total_tokens:318900, total_cost_usd:4.10, last_event_ts: iso(8,41,30), path:['PLANNING','BUILDING','REVIEWING','TESTING','REVIEWING','TESTING','RETRO','DONE'], seed:2024 },
  { name:'email-digest', state:'PLANNING', convs_done:0, convs_total:2, event_count:4, agent_done_count:0, total_tokens:5400, total_cost_usd:0.06, last_event_ts: iso(12,3,44), path:['PLANNING'], seed:555 },
  { name:'rate-limiter', state:'RETRO', convs_done:2, convs_total:2, event_count:39, agent_done_count:7, total_tokens:233100, total_cost_usd:3.05, last_event_ts: iso(11,2,18), path:['PLANNING','BUILDING','REVIEWING','TESTING','REVIEWING','TESTING','RETRO'], seed:9001 },
];

const EVENTS_BY_FEATURE = {};
FEATURE_DEFS.forEach(f => {
  EVENTS_BY_FEATURE[f.name] = f._rich ? buildFsmEvents() : genEvents(f);
});

const FEATURES = FEATURE_DEFS.map(({ path, seed, _rich, ...rest }) => rest);

const SUMMARY = {
  features: FEATURES.length,
  events: FEATURES.reduce((a,f)=>a+f.event_count,0),
  invocations: FEATURES.reduce((a,f)=>a+f.agent_done_count,0),
  total_cost: FEATURES.reduce((a,f)=>a+f.total_cost_usd,0),
};

/* state endpoint mock */
function getState(name) {
  const f = FEATURES.find(x=>x.name===name);
  if (!f) return null;
  return {
    fsm: { current: f.state, convs_done: f.convs_done, convs_total: f.convs_total, updated_at: f.last_event_ts },
    runner: f.agent_done_count > 0 ? {
      status: f.state==='DONE'?'finished':'running', iterations: f.convs_done,
      total_cost_usd: f.total_cost_usd, total_tokens: f.total_tokens, agents_done: f.agent_done_count,
    } : null,
  };
}

/* agent invocations (AGENT_DONE payloads) for a feature, oldest-first */
function getAgents(name) {
  return (EVENTS_BY_FEATURE[name] || [])
    .filter(e => e.type === 'AGENT_DONE')
    .slice().sort((a,b)=>a.seq-b.seq)
    .map(e => ({ seq: e.seq, ts: e.ts, ...e.payload }));
}

/* simple SQL mock — supports the prefilled query + basic SELECTs */
function runSql(sql) {
  const q = String(sql || '').trim();
  if (!/^select\b/i.test(q)) return { error: 'Only SELECT queries are allowed. (read-only)' };
  if (/;\s*\S/.test(q.replace(/;\s*$/, ''))) return { error: 'Multiple statements are not allowed.' };
  // Gather all events across features as fsm_events rows
  let rows = [];
  for (const fname of Object.keys(EVENTS_BY_FEATURE)) {
    for (const e of EVENTS_BY_FEATURE[fname]) {
      rows.push({ feature: fname, seq: e.seq, type: e.type, ts: e.ts, payload: JSON.stringify(e.payload) });
    }
  }
  // ORDER BY seq DESC (default behaviour of the sample query)
  if (/order\s+by\s+seq\s+desc/i.test(q)) rows.sort((a,b)=>b.seq-a.seq);
  else if (/order\s+by\s+ts\s+desc/i.test(q)) rows.sort((a,b)=> (a.ts<b.ts?1:-1));
  else if (/order\s+by\s+ts\b/i.test(q)) rows.sort((a,b)=> (a.ts>b.ts?1:-1));
  // WHERE type = '...'
  const wt = q.match(/where\s+type\s*=\s*'([^']+)'/i);
  if (wt) rows = rows.filter(r => r.type.toLowerCase() === wt[1].toLowerCase());
  const wf = q.match(/where\s+feature\s*=\s*'([^']+)'/i);
  if (wf) rows = rows.filter(r => r.feature.toLowerCase() === wf[1].toLowerCase());
  // column projection
  const colMatch = q.match(/^select\s+(.*?)\s+from\b/i);
  let cols = ['feature','seq','type','ts','payload'];
  if (colMatch && colMatch[1].trim() !== '*') {
    cols = colMatch[1].split(',').map(c=>c.trim().replace(/.*\s+as\s+/i,''));
  }
  // LIMIT
  const lim = q.match(/limit\s+(\d+)/i);
  if (lim) rows = rows.slice(0, parseInt(lim[1], 10));
  const outRows = rows.map(r => cols.map(c => (c in r ? r[c] : null)));
  return { columns: cols, rows: outRows };
}

window.DBData = {
  FEATURES, EVENTS_BY_FEATURE, SUMMARY,
  getState, getAgents, runSql,
  stageClass, stageVar, typeClass, resultClass,
  fmtMoney, fmtNum, fmtTime, shortTrace,
};
