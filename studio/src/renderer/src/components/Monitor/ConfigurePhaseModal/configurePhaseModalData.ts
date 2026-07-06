import { ADAPTER_META } from '../../../services/cliEngine'

// DERIVED from the ONE source (cliEngine.ADAPTER_META <- adapters.gen.ts <- adapters.yaml).
// Display name = the adapter's `hint`; add/enable engines by editing adapters.yaml.
export const CLI_HOSTS = ADAPTER_META.map((m) => m.hint)
export const AGENTS = ['planner', 'builder', 'reviewer', 'tester', 'retro'] as const
export const SKILLS = ['plan/storm', 'plan/scope', 'fix/build', 'team/build', 'review/quality', 'test/verify', 'retro/archive'] as const

export const HOST_TO_ADAPTER: Record<string, string> = Object.fromEntries(
  ADAPTER_META.map((m) => [m.hint, m.id]),
)

export const ADAPTER_TO_HOST: Record<string, string> = Object.fromEntries(
  ADAPTER_META.map((m) => [m.id, m.hint]),
)

export const AGENT_FILE_PATHS: Record<string, string> = {
  'planner':  'planning/planner',
  'builder':  'building/builder',
  'reviewer': 'quality/reviewer',
  'tester':   'quality/tester',
  'designer': 'building/designer',
}

export const SKILL_FILE_PATHS: Record<string, string> = {
  'fix/build':      'fix/build',
  'team/build':     'team/build',
  'plan/storm':     'planning/storm',
  'plan/scope':     'planning/plan',
  'review/quality': 'development/review',
  'test/verify':    'development/test',
  'retro/archive':  'planning/retro',
}

export const STAGE_DEFAULTS: Record<string, { agent: string; skill: string }> = {
  STORMING:  { agent: 'planner',  skill: 'plan/storm' },
  PLANNING:  { agent: 'planner',  skill: 'plan/scope' },
  BUILDING:  { agent: 'builder',  skill: 'fix/build' },
  REVIEWING: { agent: 'reviewer', skill: 'review/quality' },
  TESTING:   { agent: 'tester',   skill: 'test/verify' },
  DONE:      { agent: 'retro',    skill: 'retro/archive' },
}

export const DEFAULT_SKILL_PATHS = new Set(Object.values(SKILL_FILE_PATHS))

export const SKILL_PROMPTS: Record<string, string> = {
  'plan/storm':     '# plan/storm\nHost: Claude Code · Agent: planner\n\nRole: Stage orchestrator — Brainstorm.\nExplore the problem space. Generate options. No code yet.',
  'plan/scope':     '# plan/scope\nHost: Claude Code · Agent: planner\n\nRole: Stage orchestrator — Scope.\nDefine user stories, acceptance criteria, conversation breakdown.',
  'fix/build':      '# fix/build\nHost: Claude Code · Agent: builder\n\nRole: Stage orchestrator — Quick Fix.\nApply a single, well-scoped change. No multi-conversation\nplanning, no PROGRESS.md churn.\n\n· Read the issue description in features/<feature>/\n· Locate the code\n· Apply the minimal change',
  'team/build':     '# team/build\nHost: Claude Code · Agent: builder\n\nRole: Stage orchestrator — Build.\nFollow the implementation plan. Write tests. Ship it.',
  'review/quality': '# review/quality\nHost: Claude Code · Agent: reviewer\n\nRole: Stage orchestrator — Review.\nAdversarial code review. Find bugs, security issues, design gaps.\nWrite failures to REVIEW_FAILURES.md.',
  'test/verify':    '# test/verify\nHost: Claude Code · Agent: tester\n\nRole: Stage orchestrator — Test.\nRun acceptance criteria against implementation.\nWrite gaps to TEST_FAILURES.md.',
  'retro/archive':  '# retro/archive\nHost: Claude Code · Agent: retro\n\nRole: Stage orchestrator — Retro.\nSummarise what was built, cost, and lessons learned.',
}
