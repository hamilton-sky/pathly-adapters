import { useCallback, useEffect, useState } from 'react'
import { apiFetch, PATHLY_API_BASE } from '../../../lib/config'
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

  // Live feed: GET /events/runs?run_id=<id> (unified-control-plane T3) — any runner/comms event
  // tagged with this run_id triggers an immediate refresh instead of waiting out the 8s poll,
  // which keeps running as a fallback if the stream errors, closes, or is unavailable. No auth
  // header is sent: the server's secret middleware exempts every /events/* path, so this mirrors
  // the localhost-open EventSource pattern already used by useMonitorSession, useCommsPanel, and
  // pathlyContext.subscribeToMenuUpdates. A separate effect (keyed only on runId, not tick) keeps
  // the connection alive across poll-driven refreshes instead of reconnecting every 8s.
  useEffect(() => {
    if (!runId) return
    let es: EventSource | null = null
    try {
      es = new EventSource(`${PATHLY_API_BASE}/events/runs?run_id=${encodeURIComponent(runId)}`)
      es.onmessage = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data as string) as { type?: string }
          if (data.type === 'connected') return
        } catch { /* malformed payload — refresh anyway, the poll will settle it */ }
        refresh()
      }
      es.onerror = () => { /* EventSource auto-reconnects; the 8s poll covers any gap */ }
    } catch {
      // EventSource not available (e.g. unit test env) — the 8s poll still covers it
    }
    return () => { es?.close() }
  }, [runId, refresh])

  return { detail, loading, notFound, refresh }
}
