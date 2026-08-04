import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/config'
import type { RunDetail } from '../types'

const EMPTY: RunDetail = {
  run: null,
  stages: [],
  logs: [],
  board: [],
  artifacts: [],
  cost: { cost_usd: 0, tokens_total: 0, invocations: 0 },
}

export interface UseRunDetail {
  detail: RunDetail
  loading: boolean
  /** True when GET /runs/<id> 404s (unknown run_id — e.g. a live run not yet in run_history). */
  notFound: boolean
  refresh: () => void
}

// Fetch GET /runs/<id> for ONE run, polling every 8s (mirrors Monitor/hooks/useRecentEngines) so a
// still-running run's stages/cost refresh live. A 404 sets notFound (the page shows a friendly
// message rather than an error). Never throws — a failed fetch just leaves the last good data.
export function useRunDetail(runId: string): UseRunDetail {
  const [detail, setDetail] = useState<RunDetail>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [tick, setTick] = useState(0)
  const refresh = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    const load = (): void => {
      void apiFetch(`/runs/${encodeURIComponent(runId)}`)
        .then((r) => {
          if (r.status === 404) {
            if (!cancelled) { setNotFound(true); setLoading(false) }
            return null
          }
          return r.ok ? r.json() : null
        })
        .then((d) => {
          if (cancelled) return
          if (d != null) { setDetail(d as RunDetail); setNotFound(false) }
          setLoading(false)
        })
        .catch(() => { if (!cancelled) setLoading(false) })
    }
    load()
    const id = window.setInterval(load, 8000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [runId, tick])

  return { detail, loading, notFound, refresh }
}
