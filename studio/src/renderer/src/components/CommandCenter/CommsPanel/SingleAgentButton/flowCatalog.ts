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

/** A labelled paragraph in a flow's collapsible "About this flow" section. */
export interface FlowDetail {
  label: string
  text: string
}

export interface FlowDef {
  /** Value sent to /runner/start as `flow`. */
  key: string
  label: string
  blurb: string
  nodes: FlowNode[]
  /** Optional note about the flow's feedback loops. */
  loops?: string
  /** Richer guidance shown in the expandable "About this flow" disclosure. */
  details: FlowDetail[]
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
    details: [
      { label: 'When to use', text: 'A small, well-scoped change you already understand — a typo, a one-line bug, a quick tweak. Skips design and adversarial review to stay fast.' },
      { label: 'Produces', text: 'The fix committed on the current branch, plus a quick test pass to confirm it holds.' },
      { label: 'Good to know', text: 'No planning or design artifacts are written. If VERIFYING fails it loops straight back to FIXING.' },
    ],
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
    details: [
      { label: 'When to use', text: "A bug whose cause you don't yet know. Spends real effort reproducing and locating the root cause before touching any code." },
      { label: 'Produces', text: 'A reproduction, a root-cause note, the fix, and a verification pass — committed as it goes.' },
      { label: 'Good to know', text: 'ROOT_CAUSE_FOUND routes the work to the right fixer. VERIFYING loops back to FIXING until the fix holds.' },
    ],
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
    details: [
      { label: 'When to use', text: 'A structural question about the codebase — how does X work, is it safe to change Y — when you want understanding, not edits.' },
      { label: 'Produces', text: 'A written exploration (framing → traces → conclusions). It edits no source files.' },
      { label: 'Good to know', text: 'Read-only end to end. A good first step before planning a risky change.' },
    ],
  },
  {
    key: 'test',
    label: 'Test — build & test pipeline',
    blurb: 'Plan → build → review → test. Like team, without design or retro.',
    nodes: [
      { state: 'PLANNING', role: 'planner', agent: 'team/plan' },
      { state: 'BUILDING', role: 'builder', agent: 'team/build' },
      { state: 'REVIEWING', role: 'reviewer', agent: 'team/review' },
      { state: 'TESTING', role: 'tester', agent: 'team/test' },
      DONE,
    ],
    loops: 'REVIEWING and TESTING loop back to BUILDING on failures.',
    details: [
      { label: 'When to use', text: "A feature you want built and verified, but that doesn't need a design pass or a retrospective. Lighter than the full team flow." },
      { label: 'Produces', text: 'An implementation plan, the built feature, an adversarial review, and a test pass — committed per stage.' },
      { label: 'Good to know', text: 'REVIEWING and TESTING loop back to BUILDING on failures until both pass.' },
    ],
  },
  {
    key: 'team',
    label: 'Team — full feature pipeline',
    blurb: 'The complete pipeline: plan → design → build → review → test → retro.',
    nodes: [
      { state: 'PLANNING', role: 'planner', agent: 'team/plan' },
      { state: 'DESIGNING', role: 'designer', agent: 'team/design' },
      { state: 'BUILDING', role: 'builder', agent: 'team/build' },
      { state: 'REVIEWING', role: 'reviewer', agent: 'team/review' },
      { state: 'TESTING', role: 'tester', agent: 'team/test' },
      { state: 'RETRO', role: 'retro', agent: 'team/retro' },
      DONE,
    ],
    loops: 'REVIEWING and TESTING loop back to BUILDING until the gate passes.',
    details: [
      { label: 'When to use', text: 'A full feature from scratch — the complete pipeline. Use when the work needs design, review, tests, and a retrospective.' },
      { label: 'Produces', text: 'Stories, plan, design system, implementation, review, tests, and a retro — each stage gated and committed.' },
      { label: 'Good to know', text: 'The heaviest flow. REVIEWING/TESTING loop back to BUILDING until the verify and scope gates pass.' },
    ],
  },
]
