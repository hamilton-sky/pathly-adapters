import { useStore } from '../../store'
import { useMonitorSession } from './hooks/useMonitorSession'
import { HeaderBar } from './HeaderBar'
import { TabBar } from './TabBar'
import { PlanProgressSection } from './PlanProgressSection'
import { MetricsStrip } from './MetricsStrip'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import { HealthCheck } from './HealthCheck'
import styles from './Monitor.module.css'

export function Monitor(): JSX.Element {
  const { activeTopic, activeFlowSessions, activeMonitorTab, setActiveMonitorTab } = useStore()
  const { effectiveTopic, showTabBar } = useMonitorSession()

  if (!activeTopic) {
    return (
      <div className={styles.panel}>
        <span className={styles.placeholder}>Select a topic above to monitor</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <HeaderBar effectiveTopic={effectiveTopic} />
      {showTabBar && (
        <TabBar
          sessions={activeFlowSessions}
          activeTab={activeMonitorTab}
          onTabSelect={setActiveMonitorTab}
        />
      )}
      <PlanProgressSection topic={effectiveTopic} />
      <HealthCheck />
      <FsmView />
      <MetricsStrip />
      <EventLog />
    </div>
  )
}
