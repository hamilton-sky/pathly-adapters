import { useState } from 'react'
import { useUiStore } from '../../store/uiStore'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useDockEngines } from './useDockEngines'
import { DockCollapsed } from './DockCollapsed/DockCollapsed'
import { DockExpanded } from './DockExpanded/DockExpanded'
import { SpawnQueuePanel } from './SpawnQueuePanel'
import s from './CliMonitorBar.module.css'

// The floating CLI-engine dock ("Engines") — a compact, always-available companion to the full
// Monitor board in the Pipeline panel. Projects the authoritative spawn-gate engine list (global,
// across features) via useDockEngines; per-engine controls live in each row. The footer's "Manage
// queue" reveals the existing SpawnQueuePanel (live queue + caps). Run-starting is NOT here — it
// lives on the board (goal/task Run) — so this dock is a pure monitor + queue tool. Stays mounted
// whenever toggled open (even with no engines) so "Manage queue" is always reachable.
export function CliMonitorBar(): JSX.Element | null {
  const open = useUiStore((st) => st.cliMonitorOpen)
  const toggleCliMonitor = useUiStore((st) => st.toggleCliMonitor)
  const setActivePanel = useStore((st) => st.setActivePanel)
  const spawnQueue = useTerminalStore((st) => st.spawnQueue)
  const engines = useDockEngines()
  const [expanded, setExpanded] = useState(true)
  const [queueOpen, setQueueOpen] = useState(false)

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
    <div className={s.anchor}>
      {expanded ? (
        <DockExpanded
          engines={engines}
          queuedCount={spawnQueue.queued.length}
          queueSlot={queueOpen ? <SpawnQueuePanel spawnQueue={spawnQueue} /> : null}
          onCollapse={() => setExpanded(false)}
          onClose={toggleCliMonitor}
          onOpenMonitor={() => setActivePanel('monitor')}
          onOpenEngine={(id) => useTerminalStore.getState().openTab(id)}
          onAction={handleAction}
          onPauseAll={pauseAll}
          onManageQueue={() => setQueueOpen((v) => !v)}
        />
      ) : (
        <DockCollapsed
          engines={engines}
          onExpand={() => setExpanded(true)}
          onClose={toggleCliMonitor}
        />
      )}
    </div>
  )
}
