import { useState } from 'react'
import { useStore } from '../../store'
import { useMonitorSession } from './hooks/useMonitorSession'
import { HeaderBar } from './HeaderBar'
import { TabBar } from './TabBar'
import { FsmView } from './FsmView'
import { HealthCheck } from './HealthCheck'
import { OutputTab } from './output/OutputTab'
import { ConfigurePhaseModal } from './ConfigurePhaseModal/ConfigurePhaseModal'
import styles from './Monitor.module.css'

// The Pipeline panel: the flow's stage timeline (click a stage to configure its
// agent/skill/host) plus per-stage run output. Live telemetry (tokens/cost) lives
// in DB Explorer; the semantic activity stream lives on the Command Center board's
// Monitor lane — so this panel deliberately does NOT duplicate either.
export function Monitor(): JSX.Element {
  const { activeTopic, activeFlowSessions, activeMonitorTab, setActiveMonitorTab } = useStore()
  const { effectiveTopic, showTabBar, refresh } = useMonitorSession()
  const [configStage, setConfigStage] = useState<string | null>(null)

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
      <OutputTab />
      {configStage && (
        <ConfigurePhaseModal stage={configStage} onClose={() => setConfigStage(null)} />
      )}
    </div>
  )
}
