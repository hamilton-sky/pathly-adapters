import { useEffect, useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { apiFetch } from '../../lib/config'
import { formatRelative } from '../../utils/timestamp'
import type { DockEngine, EngineAdapter, EngineCategory, EngineRole } from './types'

interface DbRecent {
  feature: string
  agent_role: string
  provider: string
  run_id: string
  cost_usd: number
  tokens: number
  finished_at: string
  started_at: string
  scope_tier: string
}

const EMPTY: RunningEngine[] = []

/** Provider (model id) or CliAdapter → the dock's display adapter. */
function adapterFromProvider(p: string): EngineAdapter {
  const k = (p || '').toLowerCase()
  if (k.startsWith('gpt') || k.startsWith('o1') || k.startsWith('o3') || k.startsWith('codex')) return 'Codex'
  if (k.startsWith('gemini') || k === 'agy' || k.startsWith('antigravity')) return 'Gemini'
  return 'Claude'
}

// DB-backed persistent spawn history — the last N agent_invocations (survives app restarts, covers
// every run type, incl. renderer one-shots like ai-router summaries once they land in /db/recent).
// Polled every 8s while `enabled` (the dock is open) — the dock is always mounted (App.tsx) and
// returns null when closed, so gating on `enabled` stops a needless poll for a hidden dock. The
// gate's in-memory recent ring is an instant fallback before the first fetch (or when the FSM
// server is unreachable).
export function useRecentSpawns(enabled = true): DockEngine[] {
  const projectPath = useStore((s) => s.projectPath)
  const inMemory = useTerminalStore((s) => s.spawnQueue.recentEngines ?? EMPTY)
  const [db, setDb] = useState<DbRecent[]>([])

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    const load = (): void => {
      const q = projectPath
        ? `?project_root=${encodeURIComponent(projectPath)}&limit=20`
        : '?limit=20'
      void apiFetch(`/db/recent${q}`)
        .then((r) => (r.ok ? r.json() : []))
        .then((d) => { if (!cancelled && Array.isArray(d)) setDb(d) })
        .catch(() => undefined)
    }
    load()
    const id = window.setInterval(load, 8000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [projectPath, enabled])

  if (db.length > 0) {
    return db.map((r) => {
      const category = (r.scope_tier === 'project' ? 'single' : 'flow') as EngineCategory
      const ts = r.finished_at || r.started_at
      const cost = r.cost_usd > 0 ? `$${r.cost_usd.toFixed(3)}` : r.tokens ? `${r.tokens} tok` : 'done'
      return {
        id: r.run_id || `${r.feature}-${r.started_at}`,
        adapter: adapterFromProvider(r.provider),
        category,
        role: (r.agent_role || 'agent') as EngineRole,
        feature: r.feature || '(project)',
        stage: '',
        status: 'done' as const,
        elapsed: ts ? formatRelative(ts) : '-',
        sub: `${r.agent_role || 'agent'} · ${cost}`,
      }
    })
  }
  // Fallback: the gate's in-memory ring (this session) until the first DB read lands.
  return inMemory.map((e) => ({
    id: e.tabId,
    adapter: adapterFromProvider(e.adapter),
    category: (e.category ?? 'single') as EngineCategory,
    role: (e.role ?? 'agent') as EngineRole,
    feature: e.feature ?? '(project)',
    stage: '',
    status: 'done' as const,
    elapsed: e.finishedAt ? formatRelative(e.finishedAt) : '-',
    sub: 'finished',
  }))
}
