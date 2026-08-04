import { useState } from 'react'
import { useStore } from '../../store'
import { useTerminalStore } from '../../store/terminalStore'
import { useRunnerStore } from '../../store/runnerStore'
import { useMonitorEngines } from './hooks/useMonitorEngines'
import { useRecentEngines } from './hooks/useRecentEngines'
import { OutputBanner } from './output/OutputBanner/OutputBanner'
import { MonitorBoard } from './EngineBoard'
import { ConfigurePhaseModal } from './ConfigurePhaseModal/ConfigurePhaseModal'
import { FlowControlBar } from '../HQ/FlowControlBar/FlowControlBar'
import { RunDetailPage } from '../RunDetailPage'
import styles from './Monitor.module.css'

// The Pipeline ("Monitor") panel — a single full-width column: the GLOBAL engine board with its
// Live/Runs mode toggle (every running CLI + recent history + the folded /runs list), the
// conditional OutputBanner above it, and — only while a run is active — the global runner controls
// (FlowControlBar) as a slim top bar.
//
// The old right-side FlowStepsPanel dock (stage stepper + flow tabs + per-stage configure) is gone:
// its stepper's job is now the RunDetailPage "Stages" tab, per-stage config is a flow-AUTHORING
// concern (belongs with the flow editor, not a run monitor), and the runner controls — which act on
// the single active FSM run, NOT a run_id — live here at the panel level (a run_id-keyed page is the
// wrong home for a global singleton control). Clicking a run opens the shared RunDetailPage
// (entrance #1 from a live card's "Open run →", entrance #2 from a Runs-mode row). The
// ConfigurePhaseModal still opens from an engine card's "configure" action.
export function Monitor(): JSX.Element {
  const fsmState = useStore((s) => s.fsmState)
  const runnerStatus = useRunnerStore((s) => s.status)
  const [configStage, setConfigStage] = useState<string | null>(null)
  // Entrance to the shared RunDetailPage: a run_id set here swaps the panel body to the run detail
  // (the app shell stays), mirroring DBExplorerRedesign's FeatureDetailPage swap.
  const [detailRunId, setDetailRunId] = useState<string | null>(null)
  const engines = useMonitorEngines(null) // GLOBAL — every live engine, matching the dock
  const recent = useRecentEngines() // DB-backed history (finished spawns)

  // Runner controls (pause/resume/advance/reroute/retry/abort) only make sense mid-run, so the bar
  // shows ONLY while a run is active — runs are STARTED from the board's goal/task Run controls.
  const runnerActive =
    runnerStatus === 'running' ||
    runnerStatus === 'paused' ||
    runnerStatus === 'blocked' ||
    runnerStatus === 'finalizing'

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

  // Full-panel run detail swaps in over the board while the app shell stays.
  if (detailRunId) {
    return <RunDetailPage runId={detailRunId} onBack={() => setDetailRunId(null)} backLabel="Monitor" />
  }

  return (
    <div className={styles.panel}>
      <div className={styles.body}>
        <div className={styles.main}>
          <OutputBanner />

          {runnerActive && (
            <div className={styles.runnerBar}>
              <FlowControlBar />
            </div>
          )}

          {/* Global engine board — Live (per-spawn) or Runs (folded /runs), toggled in its header.
              Always mounted so the toggle is reachable with nothing live; each mode owns its empty
              state (a run can exist in /runs with no live engine — what Runs mode surfaces). */}
          <MonitorBoard engines={engines} recent={recent} onAction={handleEngineAction} onOpenRun={setDetailRunId} />
        </div>
      </div>

      {configStage && (
        <ConfigurePhaseModal stage={configStage} onClose={() => setConfigStage(null)} />
      )}
    </div>
  )
}
