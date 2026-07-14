import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { apiFetch } from '../../../lib/config'
import { formatRelative, formatClock } from '../../../utils/timestamp'
import type { EngineAdapter, EngineCategory, EngineRole, MonitorEngine } from '../EngineBoard'

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

/** Provider (model id) or CliAdapter → the board's display adapter. */
function adapterFromProvider(p: string): EngineAdapter {
  const k = (p || '').toLowerCase()
  if (k.startsWith('gpt') || k.startsWith('o1') || k.startsWith('o3') || k.startsWith('codex')) return 'Codex'
  if (k.startsWith('gemini') || k === 'agy' || k.startsWith('antigravity')) return 'Gemini'
  return 'Claude'
}

// DB-backed recent finished spawns for the board's RECENT section — GET /db/recent, with real
// cost/tokens (unlike the live cards, which read '-' until AGENT_DONE). Project-scoped to the
// active project; polled every 8s.
export function useRecentEngines(): MonitorEngine[] {
  const projectPath = useStore((s) => s.projectPath)
  const [db, setDb] = useState<DbRecent[]>([])

  useEffect(() => {
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
  }, [projectPath])

  return db.map((r) => {
    const category = (r.scope_tier === 'project' ? 'single' : 'flow') as EngineCategory
    const ts = r.finished_at || r.started_at
    const tok = r.tokens >= 1000 ? `${(r.tokens / 1000).toFixed(1)}k tok` : r.tokens ? `${r.tokens} tok` : '-'
    return {
      id: r.run_id || `${r.feature}-${r.started_at}`,
      adapter: adapterFromProvider(r.provider),
      model: r.provider || '',
      category,
      role: (r.agent_role || 'agent') as EngineRole,
      feature: r.feature || '(project)',
      stage: '',
      status: 'done' as const,
      elapsed: ts ? formatRelative(ts) : '-',
      started: r.started_at ? formatClock(r.started_at) : '-',
      tokensIn: '-',
      tokensOut: '-',
      tokens: tok,
      cost: r.cost_usd > 0 ? `$${r.cost_usd.toFixed(3)}` : '-',
      snippet: `${r.agent_role || 'agent'} · finished`,
    }
  })
}
