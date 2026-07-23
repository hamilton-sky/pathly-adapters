import { useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useMonitorSession } from './hooks/useMonitorSession'
import { useMonitorEngines } from './hooks/useMonitorEngines'
import { useRecentEngines } from './hooks/useRecentEngines'
import { OutputBanner } from './output/OutputBanner/OutputBanner'
import { MonitorBoard } from './EngineBoard'
import { ConfigurePhaseModal } from './ConfigurePhaseModal/ConfigurePhaseModal'
import { FlowStepsPanel } from './FlowStepsPanel/FlowStepsPanel'
import styles from './Monitor.module.css'

// The Pipeline panel, laid out as a row: the GLOBAL live engine board is the MAIN content (left) —
// every running CLI engine (headless or interactive, any feature or a project one-shot), in parity
// with the Engines dock; deliberately NOT feature-scoped and NOT gated behind a feature selection.
// The old feature-scoped header stack (HeaderBar / RunCostBadge / HealthCheck) is unmounted — a
// feature title above a global board was incongruous chrome; the run cost re-homed into the flow
// dock. Only the conditional OutputBanner (output → modal) remains above the board. The stage
// timeline + runner controls live in FlowStepsPanel, a collapsible RIGHT dock that renders
// whichever running flow is selected as a vertical stepper (click a stage to configure its
// agent/skill/host) with the runner controls beneath it.
export function Monitor(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const { effectiveTopic, showTabBar } = useMonitorSession()
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
      <div className={styles.body}>
        <div className={styles.main}>
          <OutputBanner />

          {/* Global engine board — every live CLI + recent history, in parity with the Engines
              dock. It's the main content of the panel now that the stage timeline moved to the
              right dock and the old feature header stack is gone. */}
          {engines.length > 0 || recent.length > 0 ? (
            <MonitorBoard engines={engines} recent={recent} onAction={handleEngineAction} />
          ) : (
            <span className={styles.placeholder}>
              No CLI engines yet — run a flow, goal, or task from the board to see it here
            </span>
          )}
        </div>

        {/* Collapsible right-side flow dock: the selected flow's vertical stepper + the runner
            controls (pause / resume / advance / reroute / retry / abort). The flow tabs inside it
            toggle which running flow the dock steps through. Replaces the old fixed top bar. */}
        <FlowStepsPanel
          effectiveTopic={effectiveTopic}
          showTabBar={showTabBar}
          onStageClick={(stage) => setConfigStage(stage)}
        />
      </div>

      {configStage && (
        <ConfigurePhaseModal stage={configStage} onClose={() => setConfigStage(null)} />
      )}
    </div>
  )
}
