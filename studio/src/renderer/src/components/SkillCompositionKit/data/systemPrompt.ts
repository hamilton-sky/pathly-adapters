// The composed system prompt = always-on base directives + one injected instruction per
// included fragment. BODY_TOKENS is the skill-body cost; replace with the measured value.
export interface SystemSegment {
  id: string
  name: string
  tokens: number
  desc: string
}

export const BODY_TOKENS = 333

export const SYSTEM_BASE: SystemSegment[] = [
  { id: 'sys-role',    name: 'Role directive',   tokens: 96, desc: 'Stage orchestrator directive. Apply the fix identified in the root-cause analysis; stay strictly within the diagnosed scope — no unrelated refactors.' },
  { id: 'sys-context', name: 'Context protocol', tokens: 74, desc: 'Before touching any code, read ROOT_CAUSE.md and REPRO.md; confirm the exact files, lines and fix approach first.' },
  { id: 'sys-run',     name: 'Run protocol',     tokens: 63, desc: 'Record each phase transition via pathly-fsm-call record-phase with the correct agent, phase and event-type.' },
]
