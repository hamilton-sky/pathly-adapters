import { useState } from 'react'
import type { FeatureData } from './dbExplorerData'
import { TRANSITIONS, AGENTS, EVENTS } from './dbExplorerData'
import { StatePill } from './StatePill'
import { TimelineTab } from './TimelineTab'
import { AgentsTab } from './AgentsTab'
import { EventsTab } from './EventsTab'
import { SqlTab } from './SqlTab'
import styles from './FeatureModal.module.css'

type TabId = 'timeline' | 'events' | 'agents' | 'sql'

interface FeatureModalProps {
  feature: FeatureData | null
  onClose: () => void
}

const TABS: { id: TabId; label: string; count?: number }[] = [
  { id: 'timeline', label: 'Timeline', count: 9 },
  { id: 'events', label: 'Events', count: 47 },
  { id: 'agents', label: 'Agents', count: 8 },
  { id: 'sql', label: 'SQL' },
]

export function FeatureModal({ feature, onClose }: FeatureModalProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabId>('timeline')

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div
      className={styles.overlay}
      {...(feature ? { 'data-open': '' } : {})}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label={feature ? `Feature details: ${feature.name}` : 'Feature details'}
    >
      {feature && (
        <div className={styles.modal}>
          <ModalHeader feature={feature} onClose={onClose} />
          <ModalTabs activeTab={activeTab} onTabChange={setActiveTab} />
          <div className={styles.mBody}>
            {activeTab === 'timeline' && <TimelineTab transitions={TRANSITIONS} />}
            {activeTab === 'events' && <EventsTab events={EVENTS} />}
            {activeTab === 'agents' && <AgentsTab agents={AGENTS} />}
            {activeTab === 'sql' && <SqlTab />}
          </div>
        </div>
      )}
    </div>
  )
}

function ModalHeader({ feature, onClose }: { feature: FeatureData; onClose: () => void }): JSX.Element {
  return (
    <div className={styles.mHead}>
      <span className={styles.mName}>{feature.name}</span>
      <StatePill state={feature.state} />
      <span className={styles.mMeta}>
        <b>{feature.cost}</b> · {feature.tokens} tokens
      </span>
      <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close modal">
        ✕
      </button>
    </div>
  )
}

function ModalTabs({ activeTab, onTabChange }: { activeTab: TabId; onTabChange: (t: TabId) => void }): JSX.Element {
  return (
    <div className={styles.mTabs}>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={styles.mTab}
          {...(activeTab === tab.id ? { 'data-active': '' } : {})}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className={styles.ct}>{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}
