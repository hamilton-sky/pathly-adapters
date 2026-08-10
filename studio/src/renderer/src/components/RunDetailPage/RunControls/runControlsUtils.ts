export type FlowAction = 'pause' | 'resume' | 'advance' | 'reroute' | 'retry'

const ACTIVE_STATUSES = new Set(['running', 'paused', 'awaiting_decision'])

/**
 * Which flow-only control buttons to show for a flow-kind run at this status. Mirrors the
 * server's gate (control/_helpers.py ACTIVE_STATUSES + runs_control.py): pause/resume/advance/
 * reroute only work against an ACTIVE registry run, retry only against a FINISHED one — so a
 * button is never shown for a call the server would reject (unsupported_for_kind/not_active).
 */
export function visibleFlowActions(status: string): FlowAction[] {
  if (status === 'running') return ['pause', 'reroute']
  if (status === 'paused') return ['resume', 'advance', 'reroute']
  if (status === 'awaiting_decision') return ['reroute']
  if (ACTIVE_STATUSES.has(status)) return []
  return ['retry']
}
