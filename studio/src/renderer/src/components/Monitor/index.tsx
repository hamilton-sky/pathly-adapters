import { useState } from 'react'
import { useStore } from '../../store'
import { useMonitorSession } from './hooks/useMonitorSession'
import { HeaderBar } from './HeaderBar'
import { TabBar } from './TabBar'
import { PlanProgressSection } from './PlanProgressSection'
import { MetricsStrip } from './MetricsStrip'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import { HealthCheck } from './HealthCheck'
import { OutputTab } from './OutputTab'
import styles from './Monitor.module.css'

export function Monitor(): JSX.Element {
  const { activeTopic, activeFlowSessions, activeMonitorTab, setActiveMonitorTab } = useStore()
  const { effectiveTopic, showTabBar } = useMonitorSession()
  const [viewTab, setViewTab] = useState<'events' | 'output'>('events')

  if (!activeTopic) {
    return (
      <div className={styles.panel}>
        <span className={styles.placeholder}>Select a topic above to monitor</span>
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
      <HeaderBar effectiveTopic={effectiveTopic} />
      <PlanProgressSection topic={effectiveTopic} />
      <HealthCheck />
      <FsmView />
      <MetricsStrip />
      {/* Sub-tab: Events | Output */}
      <div className={styles.viewTabBar}>
        <button
          type="button"
          className={`${styles.viewTab} ${viewTab === 'events' ? styles.viewTabActive : ''}`}
          onClick={() => setViewTab('events')}
        >
          Events
        </button>
        <button
          type="button"
          className={`${styles.viewTab} ${viewTab === 'output' ? styles.viewTabActive : ''}`}
          onClick={() => setViewTab('output')}
        >
          Output
        </button>
      </div>
      {viewTab === 'events' ? <EventLog /> : <OutputTab />}
    </div>
  )
}
