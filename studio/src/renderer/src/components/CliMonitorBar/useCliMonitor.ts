import { useCallback, useEffect, useRef, useState } from 'react'
import { useTerminalStore } from '../../store/terminalStore'
import type { TerminalTab } from '../../types/terminal'

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
  // Snap to nearest edge if within threshold
  if (x < SNAP) nx = 8
  else if (x > vw - BAR_W - SNAP) nx = vw - BAR_W - 8
  // 50px top offset to clear the topbar
  if (y < SNAP) ny = 50
  else if (y > vh - SNAP) ny = vh - 160
  // Clamp to viewport bounds
  nx = clamp(nx, 8, vw - BAR_W - 8)
  ny = clamp(ny, 50, vh - 60)
  return { x: nx, y: ny }
}

export interface CliSession {
  tab: TerminalTab
  elapsedS: number
}

export function useCliMonitor() {
  const tabs = useTerminalStore((s) => s.tabs)
  const runningTabs = tabs.filter((t) => t.status === 'running')
  const hasRunning = runningTabs.length > 0

  // Position state (persisted)
  const [pos, setPos] = useState<{ x: number; y: number }>(loadPos)
  const posRef = useRef(pos)
  posRef.current = pos

  const savePos = useCallback((p: { x: number; y: number }) => {
    try { localStorage.setItem(POS_KEY, JSON.stringify(p)) } catch { /* ignore */ }
    setPos(p)
    posRef.current = p
  }, [])

  // Elapsed seconds per tab — keyed by tabId
  const startedAtRef = useRef<Record<string, number>>({})
  const [elapsed, setElapsed] = useState<Record<string, number>>({})

  // Sync startedAt map with running tabs
  useEffect(() => {
    const ids = new Set(runningTabs.map((t) => t.id))
    // Add new tabs
    for (const tab of runningTabs) {
      if (!startedAtRef.current[tab.id]) {
        startedAtRef.current[tab.id] = tab.startedAt ?? Date.now()
      }
    }
    // Remove finished tabs
    for (const id of Object.keys(startedAtRef.current)) {
      if (!ids.has(id)) delete startedAtRef.current[id]
    }
  })

  // Tick every second while any engine is running
  useEffect(() => {
    if (runningTabs.length === 0) return
    const tick = () => {
      const now = Date.now()
      const next: Record<string, number> = {}
      for (const [id, start] of Object.entries(startedAtRef.current)) {
        next[id] = Math.floor((now - start) / 1000)
      }
      setElapsed(next)
    }
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [runningTabs.length])

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

  const sessions: CliSession[] = runningTabs.map((tab) => ({
    tab,
    elapsedS: elapsed[tab.id] ?? 0,
  }))

  return { sessions, hasRunning, pos, onDragStart }
}
