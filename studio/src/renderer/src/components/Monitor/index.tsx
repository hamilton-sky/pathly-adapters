import { useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useMonitorSession } from './hooks/useMonitorSession'
import { useMonitorEngines } from './hooks/useMonitorEngines'
import { HeaderBar } from './HeaderBar'
import { TabBar } from './TabBar'
import { FsmView } from './FsmView'
import { HealthCheck } from './HealthCheck'
import { OutputTab } from './output/OutputTab'
import { MonitorBoard } from './EngineBoard'
import { ConfigurePhaseModal } from './ConfigurePhaseModal/ConfigurePhaseModal'
import styles from './Monitor.module.css'

// The Pipeline panel: the flow's stage timeline (click a stage to configure its agent/skill/host)
// plus the live engine board (every CLI engine running THIS feature, grouped by how it runs) and
// per-stage run output. The board is the runtime axis; ConfigurePhaseModal is the config axis —
// a "Configure stage" control on a live engine bridges the two. Settled telemetry (tokens/cost)
// still lives in DB Explorer; the cross-feature activity stream lives on the Command Center board.
export function Monitor(): JSX.Element {
  const { activeTopic, activeFlowSessions, activeMonitorTab, setActiveMonitorTab, fsmState } = useStore()
  const { effectiveTopic, showTabBar, refresh } = useMonitorSession()
  const [configStage, setConfigStage] = useState<string | null>(null)
  const engines = useMonitorEngines(effectiveTopic)

  function handleEngineAction(engineId: string, actionId: string): void {
    const term = useTerminalStore.getState()
    switch (actionId) {
      case 'open':
        term.openTab(engineId)
        break
      case 'stop':
      case 'abort':
        // Mirror CliMonitorBar's stop: kill releases the gate slot (dropping the card from the
        // authoritative list), and updateTabStatus('done') before closeTab snapshots it to RECENT.
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
      case 'configure': {
        // The cross-link: from a live engine, open the config modal for the stage it is running.
        const eng = engines.find((e) => e.id === engineId)
        setConfigStage(String(eng?.stage || fsmState?.current || 'BUILDING'))
        break
      }
    }
  }

  if (!activeTopic) {
    return (
      <div className={styles.panel}>
        <span className={styles.placeholder}>Select a feature above to see its pipeline</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      {showTabBar && (
        <TabBar
          sessions={activeFlowSessions}
          activeTab={activeMonitorTab}
          onTabSelect={setActiveMonitorTab}
        />
      )}
      <HeaderBar effectiveTopic={effectiveTopic} onRefresh={refresh} />
      <HealthCheck />
      <FsmView onStageClick={(stage) => setConfigStage(stage)} />
      {engines.length > 0 && (
        <MonitorBoard engines={engines} onAction={handleEngineAction} />
      )}
      <OutputTab />
      {configStage && (
        <ConfigurePhaseModal stage={configStage} onClose={() => setConfigStage(null)} />
      )}
    </div>
  )
}
