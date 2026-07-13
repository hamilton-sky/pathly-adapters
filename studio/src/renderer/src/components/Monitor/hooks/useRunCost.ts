import { useEffect, useState } from 'react'
import { useTerminalStore } from '../../../store/terminalStore'
import { apiFetch } from '../../../lib/config'

export interface RunCost {
  cost_usd: number
  tokens_total: number
  invocations: number
}

// Settled, billing-reconciled per-flow cost/tokens for the active feature's most-recent run —
// GET /db/runs/<run_id>/cost. The run_id comes from the feature's live flow engine (the spawn
// gate carries it on RunningEngine); we remember the last one so the total stays visible after
// the run ends. Polls every 4s while a run is live (the settled total climbs as stages finish),
// then one final read once the engine is gone.
export function useRunCost(feature: string | null): { runId: string | null; cost: RunCost | null } {
  const liveRunId = useTerminalStore(
    (s) => s.spawnQueue.engines.find((e) => e.feature === feature && e.runId)?.runId ?? null,
  )
  const [lastRunId, setLastRunId] = useState<string | null>(null)
  useEffect(() => { setLastRunId(null) }, [feature]) // reset when the panel's feature changes
  useEffect(() => { if (liveRunId) setLastRunId(liveRunId) }, [liveRunId])
  const runId = liveRunId ?? lastRunId

  const [cost, setCost] = useState<RunCost | null>(null)
  useEffect(() => {
    if (!runId) { setCost(null); return }
    let cancelled = false
    const load = (): void => {
      void apiFetch(`/db/runs/${encodeURIComponent(runId)}/cost`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          if (!cancelled && d) {
            setCost({ cost_usd: d.cost_usd ?? 0, tokens_total: d.tokens_total ?? 0, invocations: d.invocations ?? 0 })
          }
        })
        .catch(() => undefined)
    }
    load()
    const id = liveRunId ? window.setInterval(load, 4000) : null
    return () => { cancelled = true; if (id) window.clearInterval(id) }
  }, [runId, liveRunId])

  return { runId, cost }
}
