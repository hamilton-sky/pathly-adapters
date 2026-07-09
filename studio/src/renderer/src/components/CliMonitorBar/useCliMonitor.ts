import { useCallback, useEffect, useRef, useState } from 'react'
import { useTerminalStore } from '../../store/terminalStore'
import type { SessionRecord } from '../../store/terminalStore'
import { lastNLines } from './ansiUtils'
import { loadCaps } from './SpawnQueuePanel'

const POS_KEY = 'pathly:cliMonitorPos'
const BAR_W   = 288
const SNAP    = 100

function defaultPos(): { x: number; y: number } {
  return { x: window.innerWidth - BAR_W - 16, y: window.innerHeight - 220 }
}

function loadPos(): { x: number; y: number } {
  try {
    const v = localStorage.getItem(POS_KEY)
    if (v) return JSON.parse(v) as { x: number; y: number }
  } catch { /* ignore */ }
  return defaultPos()
}

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val))
}

function snapPos(x: number, y: number): { x: number; y: number } {
  const vw = window.innerWidth
  const vh = window.innerHeight
  let nx = x
  let ny = y
  if (x < SNAP) nx = 8
  else if (x > vw - BAR_W - SNAP) nx = vw - BAR_W - 8
  if (y < SNAP) ny = 50
  else if (y > vh - SNAP) ny = vh - 160
  nx = clamp(nx, 8, vw - BAR_W - 8)
  ny = clamp(ny, 50, vh - 60)
  return { x: nx, y: ny }
}

export interface CliSession {
  tabId: string
  adapter: string
  label: string
  elapsedS: number
  lastLines: string[]
  prompt?: string
  /** True when a terminalStore tab still backs this engine (enables "open terminal"). */
  hasTab: boolean
}

export type { SessionRecord }

export function useCliMonitor() {
  const tabs = useTerminalStore((s) => s.tabs)
  const scrollbackByTabId = useTerminalStore((s) => s.scrollbackByTabId)
  const sessionHistory = useTerminalStore((s) => s.sessionHistory)
  const spawnQueue = useTerminalStore((s) => s.spawnQueue)
  // ACTIVE engines come from the main-process spawn gate (authoritative process liveness),
  // NOT from renderer tab status — so board/runner runs, editor one-shots, and manual REPLs all
  // appear identically, the header count and this list share one source, and the list survives a
  // renderer reload (engines live in the main process, this store does not).
  const engines = spawnQueue.engines
  const hasRunning = engines.length > 0

  // Live spawn-scheduler state from the main process (running / queued / paused / caps).
  useEffect(() => {
    const api = window.pathly?.terminal
    if (!api?.onSpawnState) return
    const caps = loadCaps()
    if (caps) void api.queueControl?.({ type: 'set-caps', caps })
    return api.onSpawnState((st) => useTerminalStore.getState().setSpawnQueue(st))
  }, [])

  // Position state (persisted)
  const [pos, setPos] = useState<{ x: number; y: number }>(loadPos)
  const posRef = useRef(pos)
  posRef.current = pos

  // Expand state — tracks which session ids are expanded
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const savePos = useCallback((p: { x: number; y: number }) => {
    try { localStorage.setItem(POS_KEY, JSON.stringify(p)) } catch { /* ignore */ }
    setPos(p)
    posRef.current = p
  }, [])

  // One shared per-second clock advances every elapsed timer. Each engine carries its own
  // startedAt from the gate, so no per-tab bookkeeping is needed.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (engines.length === 0) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [engines.length])

  // Drag-to-move with edge snapping
  const dragRef = useRef<{ startX: number; startY: number; initX: number; initY: number } | null>(null)

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initX: posRef.current.x,
      initY: posRef.current.y,
    }

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const nx = dragRef.current.initX + (ev.clientX - dragRef.current.startX)
      const ny = dragRef.current.initY + (ev.clientY - dragRef.current.startY)
      setPos({ x: nx, y: ny })
    }

    const onUp = (ev: MouseEvent) => {
      if (!dragRef.current) return
      const nx = dragRef.current.initX + (ev.clientX - dragRef.current.startX)
      const ny = dragRef.current.initY + (ev.clientY - dragRef.current.startY)
      savePos(snapPos(nx, ny))
      dragRef.current = null
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [savePos])

  const sessions: CliSession[] = engines.map((e) => {
    const tab = tabs.find((t) => t.id === e.tabId)
    return {
      tabId: e.tabId,
      adapter: e.adapter,
      label: e.label,
      elapsedS: Math.max(0, Math.floor((now - e.startedAt) / 1000)),
      lastLines: lastNLines(scrollbackByTabId[e.tabId] ?? [], 8),
      prompt: tab?.prompt,
      hasTab: !!tab,
    }
  })

  return { sessions, history: sessionHistory, hasRunning, spawnQueue, pos, onDragStart, expandedIds, toggleExpand }
}
