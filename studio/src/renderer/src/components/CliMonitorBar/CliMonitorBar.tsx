import { useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { useUiStore } from '../../store/uiStore'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useDockEngines } from './useDockEngines'
import { useRecentSpawns } from './useRecentSpawns'
import { useDockDrag } from './useDockDrag'
import { DockCollapsed } from './DockCollapsed/DockCollapsed'
import { DockExpanded } from './DockExpanded/DockExpanded'
import { SpawnQueuePanel } from './SpawnQueuePanel'
import s from './CliMonitorBar.module.css'

// The floating CLI-engine dock ("Engines") — a compact, always-available companion to the full
// Monitor board in the Pipeline panel. Projects the authoritative spawn-gate engine list (global,
// across features) via useDockEngines; per-engine controls live in each row. The footer's "Manage
// queue" reveals the existing SpawnQueuePanel (live queue + caps). Run-starting is NOT here — it
// lives on the board (goal/task Run) — so this dock is a pure monitor + queue tool. Draggable by
// its grip (useDockDrag); stays mounted whenever toggled open so "Manage queue" is always
// reachable even when idle.
export function CliMonitorBar(): JSX.Element | null {
  const open = useUiStore((st) => st.cliMonitorOpen)
  const toggleCliMonitor = useUiStore((st) => st.toggleCliMonitor)
  const setActivePanel = useStore((st) => st.setActivePanel)
  const spawnQueue = useTerminalStore((st) => st.spawnQueue)
  const engines = useDockEngines()
  // DB-backed finished runs (incl. renderer one-shots: ai-router summaries, editor actions) so a
  // run that has exited is still visible in the dock as history — not only while its engine is live.
  // Polled only while the dock is open.
  const recent = useRecentSpawns(open)
  const [expanded, setExpanded] = useState(true)
  const [queueOpen, setQueueOpen] = useState(false)
  const anchorRef = useRef<HTMLDivElement>(null)
  const { pos, onGripPointerDown } = useDockDrag(anchorRef)

  if (!open) return null

  function handleAction(engineId: string, actionId: string): void {
    const term = useTerminalStore.getState()
    switch (actionId) {
      case 'open':
        term.openTab(engineId)
        break
      case 'stop':
        // Mirror the panel board: kill releases the gate slot (dropping the row from the
        // authoritative list); updateTabStatus('done') before closeTab snapshots it to RECENT.
        void window.pathly.terminal.kill(engineId)
        term.updateTabStatus(engineId, 'done')
        term.closeTab(engineId)
        break
      case 'cancel':
        void window.pathly.terminal.queueControl({ type: 'cancel', tabId: engineId })
        break
      case 'up':
        void window.pathly.terminal.queueControl({ type: 'reorder', tabId: engineId, dir: 'up' })
        break
    }
  }

  function pauseAll(): void {
    void window.pathly.terminal.queueControl({ type: spawnQueue.paused ? 'resume' : 'pause' })
  }

  return (
    <div
      ref={anchorRef}
      className={s.anchor}
      {...(pos ? { 'data-dragged': '' } : {})}
      style={pos ? ({ '--dock-x': `${pos.x}px`, '--dock-y': `${pos.y}px` } as CSSProperties) : undefined}
    >
      {expanded ? (
        <DockExpanded
          engines={engines}
          recent={recent}
          queuedCount={spawnQueue.queuedEngines.length}
          queueSlot={queueOpen ? <SpawnQueuePanel spawnQueue={spawnQueue} /> : null}
          onCollapse={() => setExpanded(false)}
          onClose={toggleCliMonitor}
          onOpenMonitor={() => setActivePanel('monitor')}
          onOpenEngine={(id) => useTerminalStore.getState().openTab(id)}
          onAction={handleAction}
          onPauseAll={pauseAll}
          onManageQueue={() => setQueueOpen((v) => !v)}
          paused={spawnQueue.paused}
          onGripPointerDown={onGripPointerDown}
        />
      ) : (
        <DockCollapsed
          engines={engines}
          onExpand={() => setExpanded(true)}
          onClose={toggleCliMonitor}
          onGripPointerDown={onGripPointerDown}
        />
      )}
    </div>
  )
}
