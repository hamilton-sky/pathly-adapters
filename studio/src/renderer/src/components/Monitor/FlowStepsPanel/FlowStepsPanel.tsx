import { ChevronRight, ChevronLeft } from 'lucide-react'
import { useStore } from '../../../store'
import { TabBar } from '../TabBar'
import { FlowControlBar } from '../../HQ/FlowControlBar/FlowControlBar'
import { FlowStepper } from './FlowStepper/FlowStepper'
import { RunCostBadge } from '../RunCostBadge/RunCostBadge'
import { useFlowDock } from './hooks/useFlowDock'
import styles from './FlowStepsPanel.module.css'

interface FlowStepsPanelProps {
  effectiveTopic: string | null
  showTabBar: boolean
  onStageClick: (state: string) => void
}

/**
 * The collapsible right-side flow dock — replaces the fixed top pipeline bar. Shows whichever
 * flow the user has selected (via the flow tabs) as a vertical stepper, with the selected run's
 * settled cost (RunCostBadge, re-homed from the removed panel header) above it and the runner
 * controls beneath. Collapses to a thin rail (persisted). When several flows run in parallel,
 * the tabs toggle which run the dock steps through (they drive `effectiveTopic` in
 * useMonitorSession → the stepper data); live runs register their own tabs via
 * useLiveFlowSessions, so the dock always shows the flow the user just spawned.
 */
export function FlowStepsPanel({
  effectiveTopic,
  showTabBar,
  onStageClick,
}: FlowStepsPanelProps): JSX.Element {
  const { collapsed, toggle } = useFlowDock()
  const fsmState = useStore((s) => s.fsmState)
  const activeFlowSessions = useStore((s) => s.activeFlowSessions)
  const activeMonitorTab = useStore((s) => s.activeMonitorTab)
  const setActiveMonitorTab = useStore((s) => s.setActiveMonitorTab)

  const flowName = fsmState?.flow ?? null
  const current = fsmState?.current ?? null
  const isLive = !!current && current !== 'DONE' && current !== 'IDLE'

  if (collapsed) {
    return (
      <aside className={styles.rail}>
        <button
          type="button"
          className={styles.iconBtn}
          onClick={toggle}
          aria-label="Expand flow panel"
          aria-expanded="false"
        >
          <ChevronLeft size={16} />
        </button>
        <span className={styles.railLabel}>Flow</span>
        {isLive && <span className={styles.railDot} aria-hidden="true" />}
      </aside>
    )
  }

  return (
    <aside className={styles.dock} aria-label="Flow steps">
      <header className={styles.header}>
        <button
          type="button"
          className={styles.iconBtn}
          onClick={toggle}
          aria-label="Collapse flow panel"
          aria-expanded="true"
        >
          <ChevronRight size={16} />
        </button>
        <span className={styles.flowName}>{flowName ?? 'Flow'}</span>
        {current && (
          <span className={styles.stateBadge} {...(isLive ? { 'data-live': '' } : {})}>
            {current}
          </span>
        )}
      </header>

      {showTabBar && (
        <div className={styles.tabs}>
          <TabBar
            sessions={activeFlowSessions}
            activeTab={activeMonitorTab}
            onTabSelect={setActiveMonitorTab}
          />
        </div>
      )}

      <div className={styles.costWrap}>
        <RunCostBadge feature={effectiveTopic} />
      </div>

      <div className={styles.stepperWrap}>
        {effectiveTopic ? (
          <FlowStepper onStageClick={onStageClick} />
        ) : (
          <p className={styles.empty}>No flow running — start one from the board.</p>
        )}
      </div>

      <div className={styles.footer}>
        <FlowControlBar />
      </div>
    </aside>
  )
}
