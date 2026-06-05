/* studio-data.jsx — Monitor + Notebook mock data for Pathly Studio */

/* ---------------- Monitor ---------------- */
const MONITOR = {
  project: 'fsm-server-sqlite',
  live: true,
  convs_done: 2,
  convs_total: 2,
  conv_index: 0,
  steps_done: 3,
  steps_remaining: 4,
  stages: [
    { key: 'STORMING',  short: 'STORM', status: 'done' },
    { key: 'PLANNING',  short: 'PLANN', status: 'done' },
    { key: 'DESIGN',    short: 'DESIG', status: 'done' },
    { key: 'BUILDING',  short: 'BUILD', status: 'active' },
    { key: 'REVIEWING', short: 'REVIE', status: 'pending' },
    { key: 'TESTING',   short: 'TESTI', status: 'pending' },
    { key: 'RETRO',     short: 'RETRO', status: 'pending' },
    { key: 'DONE',      short: 'DONE',  status: 'pending' },
  ],
  stats: { tokens: '521.9k', wall: '259s', cost: '$2.82', events: 34 },
  channels: ['Health', 'FSM', 'State', 'Feedback', 'Events'],
  tabs: [
    { name: 'plan/fsm-server-sqlite', active: true, dirty: true },
    { name: 'plan/brightsky-ingest', active: false, dirty: true },
    { name: 'plan/chat-stop-token', active: false, dirty: true },
  ],
  tab_pos: '1–3 / 9',
  events: [
    { ts: '09:49:28', type: 'AGENT_DONE', agent: 'builder',  n: 1, result: 'DONE', tools: 15, wall: '257s', tok: '93.7k',  cost: '$0.5060' },
    { ts: '09:50:01', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '▸' },
    { ts: '09:51:56', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '▸' },
    { ts: '09:53:47', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '✓' },
    { ts: '09:54:13', type: 'AGENT_DONE', agent: 'reviewer', n: 1, result: 'PASS', tools: 40, wall: '251s', tok: '141.2k', cost: '$0.7627' },
    { ts: '09:54:27', type: 'PHASE', agent: 'builder', action: 'build', mark: '▸' },
    { ts: '10:03:23', type: 'PHASE', agent: 'builder', action: 'build', mark: '✓' },
    { ts: '10:03:34', type: 'AGENT_DONE', agent: 'builder',  n: 2, result: 'DONE', tools: 31, wall: '448s', tok: '157.1k', cost: '$0.8485' },
    { ts: '10:03:48', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '▸' },
    { ts: '10:05:15', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '▸' },
    { ts: '10:07:49', type: 'PHASE', agent: 'reviewer', action: 'review', mark: '✓' },
    { ts: '10:08:07', type: 'AGENT_DONE', agent: 'reviewer', n: 2, result: 'PASS', tools: 29, wall: '259s', tok: '129.8k', cost: '$0.7012' },
    { ts: '10:08:31', type: 'GATE', agent: 'tester', action: 'gate', mark: '▸' },
    { ts: '10:11:02', type: 'AGENT_DONE', agent: 'tester', n: 1, result: 'FAIL', tools: 12, wall: '148s', tok: '61.4k', cost: '$0.2310' },
  ],
  combined: '521.9k combined',
};

const WORKSPACE_TREE = [
  { label: 'Plan', tag: 'fsm-server-sqlite', open: true },
  { label: 'Debugs' },
  { label: 'Explorations' },
  { label: 'Lessons' },
  { label: 'Pipeline-walkthrough' },
];

/* ---------------- Notebook (Skill book) ---------------- */
/* Each cell: id, kind (heading|markdown|fragment), title, badge, md (full markdown) */
const SKILL = {
  breadcrumb: ['Skills', 'fix', 'build'],
  feature_path: '',
  cells: [
    {
      id: 'c1', kind: 'heading', title: 'fix/build',
      md: `# fix/build\n\nFIXING stage for the **quick-fix** flow. Fast, focused, minimal — one targeted change.\n\nInvoked by the \`team\` orchestrator when the FSM state is **BUILDING**.`,
    },
    {
      id: 'c2', kind: 'markdown', title: 'Role',
      md: `## Role\n\n**Stage orchestrator: Quick Fix.**\n\nApply a *single*, well-scoped change. No multi-conversation planning, no \`PROGRESS.md\` tracking.\n\n- Read the issue description\n- Locate the code\n- Apply the **minimal** change\n- Verify it passes`,
    },
    {
      id: 'c3', kind: 'markdown', title: 'FSM operations',
      md: `## FSM operations\n\nAll events are appended to \`<feature_path>/EVENTS.jsonl\`.\n\nEvery event **must** include \`ts\`: \`<iso-timestamp>\` using the current ISO-8601 UTC time.\n\n\`\`\`json\n{ "type": "AGENT_DONE", "ts": "2026-06-05T10:08:07Z" }\n\`\`\`\n\nState snapshots are written to \`STATE.json\` after each phase boundary.`,
    },
    {
      id: 'c4', kind: 'fragment', title: 'progress-logging', badge: 'CORE',
      subtitle: 'Live progress logging',
      md: `### progress-logging \`CORE\`\n\nLive progress logging. Each \`log-phase\` call is part of the pipeline contract.\n\n- After each phase completes, log \`log-phase PHASE_DONE <phase>\` **before** starting the next.\n- If \`pathly-fsm-call\` is unavailable, skip silently — never block execution.`,
    },
    {
      id: 'c5', kind: 'fragment', title: 'completion-report', badge: 'CORE',
      subtitle: 'Completion report (AGENT_DONE)',
      md: `### completion-report \`CORE\`\n\nEmit a single \`AGENT_DONE\` event when the stage finishes.\n\n**Required fields:** \`agent\`, \`result\`, \`total_tokens\`, \`cost_usd\`, \`wall_seconds\`, \`tool_uses\`, \`summary\`.`,
    },
    {
      id: 'c6', kind: 'fragment', title: 'scout-choreography', badge: 'CORE',
      subtitle: 'Scout choreography (analyze → scout → compress)',
      md: `### scout-choreography \`CORE\`\n\nThree-step recon: **analyze → scout → compress**.\n\n1. *analyze* — read the TODO and shared protocols\n2. *scout* — spawn sub-agents to map the codebase\n3. *compress* — fold findings into one context block`,
    },
  ],
};

window.StudioData = { MONITOR, WORKSPACE_TREE, SKILL };
