import { useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useMonitorSession } from './hooks/useMonitorSession'
import { useMonitorEngines } from './hooks/useMonitorEngines'
import { useRecentEngines } from './hooks/useRecentEngines'
import { HeaderBar } from './HeaderBar'
import { TabBar } from './TabBar'
import { FsmView } from './FsmView'
import { HealthCheck } from './HealthCheck'
import { OutputTab } from './output/OutputTab'
import { MonitorBoard } from './EngineBoard'
import { RunCostBadge } from './RunCostBadge/RunCostBadge'
import { ConfigurePhaseModal } from './ConfigurePhaseModal/ConfigurePhaseModal'
import styles from './Monitor.module.css'

// The Pipeline panel: a GLOBAL live engine board (every running CLI engine — headless or
// interactive, any feature or a project one-shot — in parity with the Engines dock) on top, then,
// when a feature is selected, that feature's stage timeline (click a stage to configure its
// agent/skill/host), settled run cost, and per-stage output. The board is deliberately NOT
// feature-scoped and NOT gated behind a feature selection: if an engine shows in the dock it must
// show here too.
export function Monitor(): JSX.Element {
  const { activeTopic, activeFlowSessions, activeMonitorTab, setActiveMonitorTab, fsmState } = useStore()
  const { effectiveTopic, showTabBar, refresh } = useMonitorSession()
  const [configStage, setConfigStage] = useState<string | null>(null)
  const engines = useMonitorEngines(null) // GLOBAL — every live engine, matching the dock
  const recent = useRecentEngines() // DB-backed history (finished spawns)

  function handleEngineAction(engineId: string, actionId: string): void {
    const term = useTerminalStore.getState()
    switch (actionId) {
      case 'open':
        term.openTab(engineId)
        break
      case 'stop':
      case 'abort':
        // Mirror the dock/CliMonitorBar: kill releases the gate slot (dropping the row from the
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
      case 'configure': {
        const eng = engines.find((e) => e.id === engineId)
        setConfigStage(String(eng?.stage || fsmState?.current || 'BUILDING'))
        break
      }
    }
  }

  return (
    <div className={styles.panel}>
      {/* Global engine board — always shows every live CLI, in parity with the Engines dock. */}
      {(engines.length > 0 || recent.length > 0) && (
        <MonitorBoard engines={engines} recent={recent} onAction={handleEngineAction} />
      )}

      {activeTopic ? (
        <>
          {showTabBar && (
            <TabBar
              sessions={activeFlowSessions}
              activeTab={activeMonitorTab}
              onTabSelect={setActiveMonitorTab}
            />
          )}
          <HeaderBar effectiveTopic={effectiveTopic} onRefresh={refresh} />
          <RunCostBadge feature={effectiveTopic} />
          <HealthCheck />
          <FsmView onStageClick={(stage) => setConfigStage(stage)} />
          <OutputTab />
        </>
      ) : (
        engines.length === 0 && recent.length === 0 && (
          <span className={styles.placeholder}>
            Select a feature above to see its pipeline — or spawn a CLI engine to see it here
          </span>
        )
      )}

      {configStage && (
        <ConfigurePhaseModal stage={configStage} onClose={() => setConfigStage(null)} />
      )}
    </div>
  )
}
