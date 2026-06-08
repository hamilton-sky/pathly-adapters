import { useState, useEffect } from 'react'
import type { FeatureData, TransitionData, AgentData, EventData } from './dbExplorerData'
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

interface ModalData {
  transitions: TransitionData[]
  agents: AgentData[]
  events: EventData[]
}

const EMPTY: ModalData = { transitions: [], agents: [], events: [] }

const STATE_COLORS: Record<string, string> = {
  PLANNING: 'var(--state-planning)',
  BUILDING: 'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING: 'var(--state-testing)',
  RETRO: 'var(--state-retro)',
  DONE: 'var(--state-done)',
}

function eventsToTransitions(events: DbEvent[]): TransitionData[] {
  return events
    .filter((e) => e.event_type === 'STAGE_ENTER')
    .map((e) => ({
      state: ((e.payload as Record<string, unknown>)['state'] as string ?? e.event_type) as TransitionData['state'],
      time: e.ts.slice(11, 19),
      duration: '—',
    }))
}

function agentsToAgentData(agents: DbAgent[]): AgentData[] {
  const totalCost = agents.reduce((s, a) => s + (a.cost_usd ?? 0), 0)
  return agents.map((a) => ({
    role: a.agent_role ?? 'unknown',
    conv: a.stage ?? '',
    stateColor: STATE_COLORS[a.stage?.toUpperCase() ?? ''] ?? 'var(--state-building)',
    costFraction: totalCost > 0 ? (a.cost_usd ?? 0) / totalCost : 0,
  }))
}

function eventsToEventData(events: DbEvent[]): EventData[] {
  return events.slice(0, 100).map((e) => ({
    time: e.ts.slice(11, 19),
    type: e.event_type,
    detail: typeof e.payload === 'object' && e.payload !== null
      ? Object.entries(e.payload).map(([k, v]) => `${k}: ${v}`).join(' · ')
      : '',
    dotColor: e.event_type === 'PIPELINE_DONE' ? 'var(--state-done)'
      : e.event_type === 'STAGE_REROUTE' ? 'var(--orange)'
      : e.event_type.includes('REVIEW') ? 'var(--state-reviewing)'
      : 'var(--state-building)',
  }))
}

export function FeatureModal({ feature, onClose }: FeatureModalProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabId>('timeline')
  const [data, setData] = useState<ModalData>(EMPTY)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!feature) { setData(EMPTY); return }
    setLoading(true)
    Promise.all([
      window.pathly.db.events(feature.name),
      window.pathly.db.agents(feature.name),
    ]).then(([rawEvents, rawAgents]) => {
      setData({
        transitions: eventsToTransitions(rawEvents),
        agents: agentsToAgentData(rawAgents),
        events: eventsToEventData(rawEvents),
      })
    }).catch(() => setData(EMPTY)).finally(() => setLoading(false))
  }, [feature?.name])

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'timeline', label: 'Timeline', count: data.transitions.length || undefined },
    { id: 'events', label: 'Events', count: data.events.length || undefined },
    { id: 'agents', label: 'Agents', count: data.agents.length || undefined },
    { id: 'sql', label: 'SQL' },
  ]

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
          <ModalTabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
          <div className={styles.mBody}>
            {loading
              ? <div className={styles.mLoading}>Loading…</div>
              : <>
                  {activeTab === 'timeline' && <TimelineTab transitions={data.transitions} />}
                  {activeTab === 'events' && <EventsTab events={data.events} />}
                  {activeTab === 'agents' && <AgentsTab agents={data.agents} />}
                  {activeTab === 'sql' && <SqlTab />}
                </>
            }
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

interface ModalTabsProps {
  tabs: { id: TabId; label: string; count?: number }[]
  activeTab: TabId
  onTabChange: (t: TabId) => void
}

function ModalTabs({ tabs, activeTab, onTabChange }: ModalTabsProps): JSX.Element {
  return (
    <div className={styles.mTabs}>
      {tabs.map((tab) => (
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
