import { useState } from 'react'
import { apiRunAction, apiStopRun } from '../../../../store/commsApi'
import type { RunDetailRun } from '../../types'

export type RunAction = 'stop' | 'pause' | 'resume' | 'advance' | 'reroute' | 'retry'

export interface UseRunControls {
  /** The action currently in flight (disables every button so only one runs at a time), or null. */
  pending: RunAction | null
  runStop: () => Promise<void>
  runPause: () => Promise<void>
  runResume: () => Promise<void>
  runAdvance: () => Promise<void>
  runReroute: (adapter: string) => Promise<void>
  runRetry: () => Promise<void>
}

// Retry restarts the SAME flow fresh (control/_helpers.py::handle_retry requires
// flow/project_root/max_iterations/max_cost_usd) — RunDetail carries the first two (a flow-kind
// run's `adapter` column IS the flow name, per run-identity) but not the original run's
// iteration/cost caps, so this mirrors apiStartFlow's own defaults (50 / $10).
const RETRY_MAX_ITERATIONS = 50
const RETRY_MAX_COST_USD = 10

// Dispatches every RunDetail control action through one pending-state gate (generalizes
// RunDetailPage's original `stopping` flag to N actions) and calls onRefresh() after each lands,
// so the button set (visibleFlowActions) re-gates against the fresh status immediately.
export function useRunControls(
  runId: string,
  run: RunDetailRun | null,
  onRefresh: () => void,
): UseRunControls {
  const [pending, setPending] = useState<RunAction | null>(null)

  async function dispatch(action: RunAction, call: () => Promise<boolean>): Promise<void> {
    setPending(action)
    await call()
    setPending(null)
    onRefresh()
  }

  return {
    pending,
    runStop: () => dispatch('stop', () => apiStopRun(runId)),
    runPause: () => dispatch('pause', () => apiRunAction(runId, 'pause')),
    runResume: () => dispatch('resume', () => apiRunAction(runId, 'resume')),
    runAdvance: () => dispatch('advance', () => apiRunAction(runId, 'advance')),
    runReroute: (adapter: string) =>
      dispatch('reroute', () => apiRunAction(runId, 'reroute', { adapter })),
    runRetry: () =>
      dispatch('retry', () =>
        apiRunAction(runId, 'retry', {
          flow: run?.adapter ?? '',
          project_root: run?.project_root ?? '',
          max_iterations: RETRY_MAX_ITERATIONS,
          max_cost_usd: RETRY_MAX_COST_USD,
        }),
      ),
  }
}
