/* Catalog + default data for the Configure-phase modal.
   Kept local so the component family is self-contained and reusable;
   pass your own `hosts` / `agents` / `skills` / `skillPrompt` props to
   override any of it at runtime. */

import type { StageName, PhaseConfig } from './types'

export const CLI_HOSTS = ['Claude Code', 'Codex', 'Copilot', 'Antigravity'] as const

export const AGENTS = ['planner', 'builder', 'reviewer', 'tester', 'retro'] as const

export const SKILLS = [
  'plan/storm',
  'plan/scope',
  'fix/build',
  'team/build',
  'review/quality',
  'test/verify',
  'retro/archive',
] as const

export const STAGE_DEFAULTS: Record<StageName, Pick<PhaseConfig, 'agent' | 'skill'>> = {
  STORMING:  { agent: 'planner',  skill: 'plan/storm' },
  PLANNING:  { agent: 'planner',  skill: 'plan/scope' },
  BUILDING:  { agent: 'builder',  skill: 'fix/build' },
  REVIEWING: { agent: 'reviewer', skill: 'review/quality' },
  TESTING:   { agent: 'tester',   skill: 'test/verify' },
  DONE:      { agent: 'retro',    skill: 'retro/archive' },
}

/** Fallback markdown previews when no live skill text is supplied. */
export const SKILL_PROMPTS: Record<string, string> = {
  'plan/storm':
    '# plan/storm\n\nRole: Stage orchestrator — **Brainstorm**.\nExplore the problem space. Generate options. No code yet.',
  'plan/scope':
    '# plan/scope\n\nRole: Stage orchestrator — **Scope**.\nDefine user stories, acceptance criteria, conversation breakdown.',
  'fix/build':
    '# fix/build\n\n**FIXING** stage for quick-fix flow. Fast, focused, minimal — one targeted change.\n\nParse `$ARGUMENTS` : `TOPIC` (the fix identifier).\n\n- Read the issue description in `plans/<feature>/`\n- Locate the code\n- Apply the minimal change — no multi-conversation planning',
  'team/build':
    '# team/build\n\nRole: Stage orchestrator — **Build**.\nFollow the implementation plan. Write tests. Ship it.',
  'review/quality':
    '# review/quality\n\nRole: Stage orchestrator — **Review**.\nAdversarial code review. Find bugs, security issues, design gaps.',
  'test/verify':
    '# test/verify\n\nRole: Stage orchestrator — **Test**.\nRun acceptance criteria against implementation.',
  'retro/archive':
    '# retro/archive\n\nRole: Stage orchestrator — **Retro**.\nSummarise what was built, cost, and lessons learned.',
}
