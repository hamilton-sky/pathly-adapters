import type { DecomposeMode } from '../../../../store/commsApi'

// Three decompose rigor tiers — one planner agent, increasing depth.
// Quick = bare task list; Plan = full plan + wired DAG; Consultation = full team.
// Re-exported here so both EvalConfigPopover and any other consumer import from one place.
export const MODE_OPTIONS: { value: DecomposeMode; label: string; hint: string }[] = [
  { value: 'planner', label: 'Quick', hint: 'Fast · bare task list' },
  { value: 'plan', label: 'Full', hint: 'One planner · full plan + wired DAG' },
  { value: 'consultation', label: 'Consultation', hint: 'Deep · full team' },
]
