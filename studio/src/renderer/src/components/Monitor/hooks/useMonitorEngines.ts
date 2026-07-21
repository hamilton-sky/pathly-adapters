import { useEffect, useMemo, useState } from 'react'
import { useStore } from '../../../store'
import { useTerminalStore } from '../../../store/terminalStore'
import { lastNLines } from '../../CliMonitorBar/ansiUtils'
import { fmtElapsed } from '../../shared/RunPill/progress'
import { formatClock } from '../../../utils/timestamp'
import type { EngineAdapter, EngineCategory, EngineRole, MonitorEngine } from '../EngineBoard'

/** Map the gate's lowercase CliAdapter id to the board's display adapter. Unknown → Claude. */
function toEngineAdapter(id: string): EngineAdapter {
  const k = id.toLowerCase()
  if (k.startsWith('codex')) return 'Codex'
  if (k === 'agy' || k.startsWith('gemini') || k.startsWith('antigravity')) return 'Gemini'
  return 'Claude'
}

// Live board rows for one feature, projected from the authoritative spawn gate (the same
// `spawnQueue.engines` list CliMonitorBar reads) so the board, the header count, and the CLI
// monitor all share one source and survive a renderer reload. Filtered to `feature` so it
// matches the pipeline timeline it sits under. Running engines have no settled token/cost until
// AGENT_DONE, so those read '-'; flow engines inherit the panel's current FSM stage.
export function useMonitorEngines(feature: string | null): MonitorEngine[] {
  const engines = useTerminalStore((s) => s.spawnQueue.engines)
  const queued = useTerminalStore((s) => s.spawnQueue.queuedEngines)
  const scrollbackByTabId = useTerminalStore((s) => s.scrollbackByTabId)
  const tabs = useTerminalStore((s) => s.tabs)
  const fsmState = useStore((s) => s.fsmState)

  // Mirror the live spawn state from the main process (same wiring CliMonitorBar uses) so the
  // board updates even when the floating CLI monitor is closed.
  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api?.onSpawnState) return
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

  return useMemo(() => {
    const currentStage = (fsmState?.current ?? '').toUpperCase()
    const rows: MonitorEngine[] = []
    // Dedupe by tabId: as a run starts it briefly appears in BOTH the running and queued maps,
    // and one tab must never yield two rows — that collides React keys in EngineSection (cards
    // duplicated or dropped). Running is walked first, so it wins over a stale queued twin.
    const seen = new Set<string>()
    for (const e of engines) {
      // Feature-scoped panel: only this feature's engines. Untagged one-shots (editor/AI actions
      // on '(project)') belong to the global CLI monitor, not this pipeline.
      if (feature && e.feature !== feature) continue
      if (seen.has(e.tabId)) continue
      seen.add(e.tabId)
      const category = (e.category ?? 'single') as EngineCategory
      const snippet =
        lastNLines(scrollbackByTabId[e.tabId] ?? [], 1)[0] ??
        tabs.find((t) => t.id === e.tabId)?.prompt?.slice(0, 80) ??
        '…'
      rows.push({
        id: e.tabId,
        adapter: toEngineAdapter(e.adapter),
        category,
        role: (e.role ?? (category === 'flow' ? 'runner' : 'agent')) as EngineRole,
        feature: e.feature ?? '(project)',
        stage: feature && category === 'flow' ? currentStage : '',
        status: 'running',
        elapsed: fmtElapsed(Math.max(0, Math.floor((now - e.startedAt) / 1000))),
        started: formatClock(e.startedAt),
        tokensIn: '-',
        tokensOut: '-',
        tokens: '-',
        cost: '-',
        snippet,
      })
    }
    for (const e of queued) {
      // Same feature scoping — a queued flow stage for this feature shows; global one-shots don't.
      if (feature && e.feature !== feature) continue
      if (seen.has(e.tabId)) continue
      seen.add(e.tabId)
      const category = (e.category ?? 'single') as EngineCategory
      rows.push({
        id: e.tabId,
        adapter: toEngineAdapter(e.adapter),
        category,
        role: (e.role ?? (category === 'flow' ? 'runner' : 'agent')) as EngineRole,
        feature: e.feature ?? '(project)',
        stage: feature && category === 'flow' ? currentStage : '',
        status: 'queued',
        elapsed: '-',
        started: '-',
        tokensIn: '-',
        tokensOut: '-',
        tokens: '-',
        cost: '-',
        snippet: 'queued · waiting for a slot',
      })
    }
    return rows
  }, [engines, queued, scrollbackByTabId, tabs, now, feature, fsmState])
}
