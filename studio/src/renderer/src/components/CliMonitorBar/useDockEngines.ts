import { useEffect, useMemo, useState } from 'react'
import { useTerminalStore } from '../../store/terminalStore'
import { lastNLines } from './ansiUtils'
import { fmtElapsed } from '../shared/RunPill/progress'
import { formatRelative } from '../../utils/timestamp'
import { loadCaps } from './SpawnQueuePanel'
import type { EngineAdapter, EngineCategory, EngineRole, DockEngine } from './types'

/** Map the gate's lowercase CliAdapter id to the dock's display adapter. Unknown → Claude. */
function toEngineAdapter(id: string): EngineAdapter {
  const k = id.toLowerCase()
  if (k.startsWith('codex')) return 'Codex'
  if (k === 'agy' || k.startsWith('gemini') || k.startsWith('antigravity')) return 'Gemini'
  return 'Claude'
}

function baseRow(e: RunningEngine): Omit<DockEngine, 'status' | 'elapsed' | 'sub'> {
  const category = (e.category ?? 'single') as EngineCategory
  return {
    id: e.tabId,
    adapter: toEngineAdapter(e.adapter),
    category,
    role: (e.role ?? (category === 'flow' ? 'runner' : 'agent')) as EngineRole,
    feature: e.feature ?? '(project)',
    stage: '',
  }
}

// Engine lists for the floating dock, projected from the authoritative spawn gate:
//  • live   = running + queued engines (every CLI, across all features — parity with the panel board)
//  • recent = the gate's bounded history of finished engines (survives a renderer reload)
export function useDockEngines(): { live: DockEngine[]; recent: DockEngine[] } {
  const engines = useTerminalStore((s) => s.spawnQueue.engines)
  const queued = useTerminalStore((s) => s.spawnQueue.queuedEngines)
  const recent = useTerminalStore((s) => s.spawnQueue.recentEngines)
  const scrollbackByTabId = useTerminalStore((s) => s.scrollbackByTabId)
  const tabs = useTerminalStore((s) => s.tabs)

  // Mirror the main-process spawn state into the store, and push persisted caps once on mount.
  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api?.onSpawnState) return
    const caps = loadCaps()
    if (caps) void api.queueControl?.({ type: 'set-caps', caps })
    return api.onSpawnState((st) => useTerminalStore.getState().setSpawnQueue(st))
  }, [])

  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (engines.length === 0) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [engines.length])

  return useMemo(() => {
    const live: DockEngine[] = [
      ...engines.map((e) => ({
        ...baseRow(e),
        status: 'running' as const,
        elapsed: fmtElapsed(Math.max(0, Math.floor((now - e.startedAt) / 1000))),
        sub:
          lastNLines(scrollbackByTabId[e.tabId] ?? [], 1)[0] ??
          tabs.find((t) => t.id === e.tabId)?.prompt?.slice(0, 80) ??
          '…',
      })),
      ...queued.map((e) => ({
        ...baseRow(e),
        status: 'queued' as const,
        elapsed: '-',
        sub: 'queued · waiting for a slot',
      })),
    ]
    const recentRows: DockEngine[] = recent.map((e) => ({
      ...baseRow(e),
      status: 'done' as const,
      elapsed: e.finishedAt ? formatRelative(e.finishedAt) : '-',
      sub: 'finished',
    }))
    return { live, recent: recentRows }
  }, [engines, queued, recent, scrollbackByTabId, tabs, now])
}
