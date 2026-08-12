import type { FsmState, FsmEvent } from '../../../types'

type StepStatus = 'completed' | 'active' | 'active-retry' | 'pending'

export interface FlowStep {
  state: string
  role: string
  status: StepStatus
  retryCount: number
}

// Shown only when a flow declares no states at all (server/DB unavailable).
const DEFAULT_STATES = ['STORMING', 'PLANNING', 'BUILDING', 'REVIEWING', 'DONE']

// Fallback role labels for flows that carry no role_map (mirrors FsmView's STAGE_AGENTS).
const STAGE_AGENTS: Record<string, string> = {
  STORMING: 'planner',
  PLANNING: 'planner',
  DESIGNING: 'designer',
  BUILDING: 'builder',
  REVIEWING: 'reviewer',
  TESTING: 'tester',
  RETRO: 'retro',
  DONE: 'retro',
}

/**
 * Derive the ordered, decorated steps for the running flow — the SAME logic FsmView uses,
 * extracted so the vertical dock stepper renders identically for ANY flow (built-in or
 * user-created), driven purely by the flow's own `pipelineStates`. Gate / terminal-precursor
 * pseudo-states (NO_DAG_SEEDED, NO_GOALS_SEEDED, …) that carry no role are dropped when the
 * flow declares roles — always keeping DONE and the live current state so the timeline stays
 * honest. A backward transition (REVIEWING → BUILDING) is counted as a retry on the target.
 */
export function deriveFlowSteps(
  pipelineStates: string[],
  stageRoles: Record<string, string>,
  fsmState: FsmState | null,
  events: FsmEvent[],
): FlowStep[] {
  const hasRoles = Object.keys(stageRoles).length > 0
  const current = (fsmState?.current ?? '').toUpperCase()
  const raw = (pipelineStates.length > 0 ? pipelineStates : DEFAULT_STATES).map((s) =>
    s.replace(/^[-\s]+/, '').trim(),
  )
  const states = hasRoles
    ? raw.filter((s) => s in stageRoles || s === 'DONE' || s === current)
    : raw

  const retryMap: Record<string, number> = {}
  for (const ev of events) {
    if (ev.type === 'STATE_TRANSITION' && ev.from && ev.to) {
      const from = String(ev.from).toUpperCase()
      const to = String(ev.to).toUpperCase()
      const fromIdx = states.indexOf(from)
      const toIdx = states.indexOf(to)
      if (fromIdx > toIdx && toIdx >= 0) retryMap[to] = (retryMap[to] ?? 0) + 1
    }
  }

  const isIdle = !current || current === 'IDLE'
  const activeIdx = isIdle ? -1 : states.indexOf(current)

  return states.map((state, idx) => {
    const retryCount = retryMap[state] ?? 0
    const status: StepStatus = isIdle
      ? 'pending'
      : idx < activeIdx
        ? 'completed'
        : idx === activeIdx
          ? retryCount > 0
            ? 'active-retry'
            : 'active'
          : 'pending'
    return {
      state,
      role: (hasRoles ? stageRoles[state] : STAGE_AGENTS[state]) ?? '',
      status,
      retryCount,
    }
  })
}
