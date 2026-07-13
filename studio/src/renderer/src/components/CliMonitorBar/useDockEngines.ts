import { useEffect, useMemo, useState } from 'react'
import { useTerminalStore } from '../../store/terminalStore'
import { lastNLines } from './ansiUtils'
import { fmtElapsed } from '../shared/RunPill/progress'
import { loadCaps } from './SpawnQueuePanel'
import type { EngineAdapter, EngineCategory, EngineRole, DockEngine } from './types'

/** Map the gate's lowercase CliAdapter id to the dock's display adapter. Unknown → Claude. */
function toEngineAdapter(id: string): EngineAdapter {
  const k = id.toLowerCase()
  if (k.startsWith('codex')) return 'Codex'
  if (k === 'agy' || k.startsWith('gemini') || k.startsWith('antigravity')) return 'Gemini'
  return 'Claude'
}

// Global live-engine list for the floating dock — every running CLI engine across ALL features
// (unlike the Pipeline panel's feature-scoped board), projected from the authoritative spawn gate
// (spawnQueue.engines) so the dock, the panel board, and the header count all agree and survive a
// renderer reload. Stage is left blank here (the dock spans features, so there's no single FSM
// stage to attribute).
export function useDockEngines(): DockEngine[] {
  const engines = useTerminalStore((s) => s.spawnQueue.engines)
  const scrollbackByTabId = useTerminalStore((s) => s.scrollbackByTabId)
  const tabs = useTerminalStore((s) => s.tabs)

  // Mirror the main-process spawn state into the store, and push persisted caps once on mount
  // (same wiring the old bar used) so the dock works even when opened standalone.
  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api?.onSpawnState) return
    const caps = loadCaps()
    if (caps) void api.queueControl?.({ type: 'set-caps', caps })
    return api.onSpawnState((st) => useTerminalStore.getState().setSpawnQueue(st))
  }, [])

  // Shared per-second clock so elapsed timers advance while engines are live.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (engines.length === 0) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [engines.length])

  return useMemo(
    () =>
      engines.map((e) => {
        const category = (e.category ?? 'single') as EngineCategory
        const sub =
          lastNLines(scrollbackByTabId[e.tabId] ?? [], 1)[0] ??
          tabs.find((t) => t.id === e.tabId)?.prompt?.slice(0, 80) ??
          '…'
        return {
          id: e.tabId,
          adapter: toEngineAdapter(e.adapter),
          category,
          role: (e.role ?? (category === 'flow' ? 'runner' : 'agent')) as EngineRole,
          feature: e.feature ?? '(project)',
          stage: '',
          status: 'running' as const,
          elapsed: fmtElapsed(Math.max(0, Math.floor((now - e.startedAt) / 1000))),
          sub,
        }
      }),
    [engines, scrollbackByTabId, tabs, now],
  )
}
