import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../../../../store'
import { apiFetch } from '../../../../lib/config'
import type { RunSummary } from '../types'

const EMPTY: RunSummary[] = []

// GET /runs?project_root=…&limit=50 — the folded run list (one row per top-level run). Polled every
// 8s (mirrors useRecentEngines / useRunDetail) ONLY while `enabled` — MonitorBoard passes
// `mode === 'runs'`, so the poll starts when the user opens Runs mode and never runs for the
// hidden Live board. Never throws; a failed fetch leaves the last good data. `refetch` bumps a
// nonce to re-run the effect immediately (and restart the 8s interval) — used by the New-run
// launcher (T6) so a just-started run appears without waiting for the next poll tick.
export function useRuns(enabled: boolean): { runs: RunSummary[]; loading: boolean; refetch: () => void } {
  const projectPath = useStore((s) => s.projectPath)
  const [runs, setRuns] = useState<RunSummary[]>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    const load = (): void => {
      const q = projectPath
        ? `?project_root=${encodeURIComponent(projectPath)}&limit=50`
        : '?limit=50'
      void apiFetch(`/runs${q}`)
        .then((r) => (r.ok ? r.json() : []))
        .then((d) => {
          if (cancelled) return
          if (Array.isArray(d)) setRuns(d as RunSummary[])
          setLoading(false)
        })
        .catch(() => { if (!cancelled) setLoading(false) })
    }
    load()
    const id = window.setInterval(load, 8000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [enabled, projectPath, nonce])

  const refetch = useCallback(() => setNonce((n) => n + 1), [])

  return { runs, loading, refetch }
}
