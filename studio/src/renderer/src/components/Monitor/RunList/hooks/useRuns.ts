import { useEffect, useState } from 'react'
import { useStore } from '../../../../store'
import { apiFetch } from '../../../../lib/config'
import type { RunSummary } from '../types'

const EMPTY: RunSummary[] = []

// GET /runs?project_root=…&limit=50 — the folded run list (one row per top-level run). Polled every
// 8s (mirrors useRecentEngines / useRunDetail) ONLY while `enabled` — MonitorBoard passes
// `mode === 'runs'`, so the poll starts when the user opens Runs mode and never runs for the
// hidden Live board. Never throws; a failed fetch leaves the last good data.
export function useRuns(enabled: boolean): { runs: RunSummary[]; loading: boolean } {
  const projectPath = useStore((s) => s.projectPath)
  const [runs, setRuns] = useState<RunSummary[]>(EMPTY)
  const [loading, setLoading] = useState(true)

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
  }, [enabled, projectPath])

  return { runs, loading }
}
