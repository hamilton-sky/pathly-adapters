// Frontend catalog of board-scoped flows — the flows that run on a topic, not a
// goal/DAG. Mirrors src/pathly_data/core/flows/*.flow.yaml (states + role_map +
// agent_map) so the launcher can preview a flow without a backend round-trip.
// There is no flow-list endpoint yet — keep this in sync if the YAML changes.

export interface FlowNode {
  /** FSM state name (e.g. BUILDING). */
  state: string
  /** Human role from the flow's role_map (e.g. builder). */
  role: string
  /** Skill/agent from agent_map that runs the stage. '' for the terminal node. */
  agent: string
  /** True for the terminal DONE node. */
  terminal?: boolean
}

export interface FlowDef {
  /** Value sent to /runner/start as `flow`. */
  key: string
  label: string
  blurb: string
  nodes: FlowNode[]
  /** Optional note about the flow's feedback loops. */
  loops?: string
}

const DONE: FlowNode = { state: 'DONE', role: 'done', agent: '', terminal: true }

export const BOARD_FLOWS: FlowDef[] = [
  {
    key: 'quick-fix',
    label: 'Quick fix — fast small change',
    blurb: 'Scope a small change, fix it, verify. No design or review stage.',
    nodes: [
      { state: 'SCOPING', role: 'scout', agent: 'scout' },
      { state: 'FIXING', role: 'builder', agent: 'fix/build' },
      { state: 'VERIFYING', role: 'tester', agent: 'tester' },
      DONE,
    ],
    loops: 'VERIFYING bounces back to FIXING until tests pass.',
  },
  {
    key: 'debug',
    label: 'Debug — find & fix a bug',
    blurb: 'Investigate, reproduce, locate the root cause, fix it, then verify.',
    nodes: [
      { state: 'INVESTIGATING', role: 'scout', agent: 'scout' },
      { state: 'REPRODUCING', role: 'tester', agent: 'tester' },
      { state: 'ROOT_CAUSE_FOUND', role: 'router', agent: 'README_routing' },
      { state: 'FIXING', role: 'builder', agent: 'debug/build' },
      { state: 'VERIFYING', role: 'reviewer', agent: 'debug/verify' },
      DONE,
    ],
    loops: 'VERIFYING returns to FIXING if the fix does not hold.',
  },
  {
    key: 'explore',
    label: 'Explore — read-only investigation',
    blurb: 'Frame a question, analyze and trace code paths, write conclusions. Touches no source.',
    nodes: [
      { state: 'FRAMING', role: 'explorer', agent: 'explorer' },
      { state: 'ANALYZING', role: 'explorer', agent: 'explorer' },
      { state: 'TRACING', role: 'explorer', agent: 'explorer' },
      { state: 'CONCLUDING', role: 'explorer', agent: 'explorer' },
      DONE,
    ],
  },
  {
    key: 'test',
    label: 'Test — build & test pipeline',
    blurb: 'Storm → plan → build → review → test. Like team, without design or retro.',
    nodes: [
      { state: 'STORMING', role: 'discoverer', agent: 'team/discover' },
      { state: 'PLANNING', role: 'planner', agent: 'team/plan' },
      { state: 'BUILDING', role: 'builder', agent: 'team/build' },
      { state: 'REVIEWING', role: 'reviewer', agent: 'team/review' },
      { state: 'TESTING', role: 'tester', agent: 'team/test' },
      DONE,
    ],
    loops: 'REVIEWING and TESTING loop back to BUILDING on failures.',
  },
  {
    key: 'team',
    label: 'Team — full feature pipeline',
    blurb: 'The complete pipeline: storm → plan → design → build → review → test → retro.',
    nodes: [
      { state: 'STORMING', role: 'discoverer', agent: 'team/discover' },
      { state: 'PLANNING', role: 'planner', agent: 'team/plan' },
      { state: 'DESIGNING', role: 'designer', agent: 'team/design' },
      { state: 'BUILDING', role: 'builder', agent: 'team/build' },
      { state: 'REVIEWING', role: 'reviewer', agent: 'team/review' },
      { state: 'TESTING', role: 'tester', agent: 'team/test' },
      { state: 'RETRO', role: 'retro', agent: 'team/retro' },
      DONE,
    ],
    loops: 'REVIEWING and TESTING loop back to BUILDING until the gate passes.',
  },
]
