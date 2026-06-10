import { useState, useEffect } from 'react'
import type { FeatureData, TransitionData } from '../dbExplorerData'
import { StatePill } from '../StatePill'
import { TimelineTab } from '../TimelineTab'
import { AgentsTab } from '../AgentsTab'
import { EventsTab } from '../EventsTab'
import { InspectTab } from '../InspectTab'
import { TracesTab } from '../TracesTab'
import { fetchPricingTable } from '../costUtils'
import type { PricingTable } from '../costUtils'
import styles from './FeatureModal.module.css'

type TabId = 'timeline' | 'events' | 'agents' | 'inspect' | 'traces'

interface FeatureModalProps {
  feature: FeatureData | null
  onClose: () => void
}

interface ModalData {
  transitions: TransitionData[]
  rawEvents: DbEvent[]
  otelSpans: DbOtelSpan[]
}

const EMPTY: ModalData = { transitions: [], rawEvents: [], otelSpans: [] }

function calcDuration(from: string, to: string): string {
  const diff = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000)
  if (diff <= 0) return '—'
  const m = Math.floor(diff / 60)
  return m > 0 ? `${m}m ${diff % 60}s` : `${diff}s`
}

function eventsToTransitions(events: DbEvent[]): TransitionData[] {
  const stateEvents = events.filter((e) => e.event_type === 'STATE_TRANSITION')
  return stateEvents.map((e, i) => {
    const payload = e.payload as Record<string, unknown>
    const state = ((payload['to'] as string) ?? '').toUpperCase()
    const next = stateEvents[i + 1]
    return {
      state: (state || 'PLANNING') as TransitionData['state'],
      time: e.ts.slice(11, 19),
      duration: next ? calcDuration(e.ts, next.ts) : '—',
    }
  })
}

function exportJson(feature: FeatureData, data: ModalData): void {
  const payload = { feature, transitions: data.transitions, events: data.rawEvents }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${feature.name}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export function FeatureModal({ feature, onClose }: FeatureModalProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabId>('timeline')
  const [data, setData] = useState<ModalData>(EMPTY)
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [pricingTable, setPricingTable] = useState<PricingTable | null>(null)

  useEffect(() => {
    fetchPricingTable().then(setPricingTable)
  }, [])

  useEffect(() => {
    if (!feature) { setData(EMPTY); return }
    setLoading(true)
    Promise.all([
      window.pathly.db.events(feature.name),
      window.pathly.db.otel(feature.name).catch(() => [] as DbOtelSpan[]),
    ])
      .then(([rawEvents, otelSpans]) => {
        setData({ transitions: eventsToTransitions(rawEvents), rawEvents, otelSpans })
      })
      .catch(() => setData(EMPTY))
      .finally(() => setLoading(false))
  }, [feature?.name, refreshKey])

  const agentCount = data.rawEvents.filter((e) => e.event_type === 'AGENT_DONE').length

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'timeline', label: 'Timeline', count: data.transitions.length || undefined },
    { id: 'events',   label: 'Events',   count: data.rawEvents.length || undefined },
    { id: 'agents',   label: 'Agents',   count: agentCount || undefined },
    { id: 'traces',   label: 'Traces',   count: data.otelSpans.length || undefined },
    { id: 'inspect',  label: 'Inspect' },
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
          <ModalActions
            feature={feature}
            onRefresh={() => setRefreshKey((k) => k + 1)}
            onExport={() => exportJson(feature, data)}
          />
          <ModalTabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
          <div className={styles.mBody}>
            {loading
              ? <div className={styles.mLoading}>Loading…</div>
              : <>
                  {activeTab === 'timeline' && <TimelineTab transitions={data.transitions} />}
                  {activeTab === 'events'   && <EventsTab events={data.rawEvents} />}
                  {activeTab === 'agents'   && <AgentsTab events={data.rawEvents} pricingTable={pricingTable} />}
                  {activeTab === 'traces'   && <TracesTab spans={data.otelSpans} />}
                  {activeTab === 'inspect'  && <InspectTab events={data.rawEvents} pricingTable={pricingTable} />}
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
        convs {feature.done}/{feature.total}
        {' · '}events {feature.events}
        {' · '}cost <b>{feature.cost}</b>
      </span>
      <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Close modal">
        ✕
      </button>
    </div>
  )
}

interface ModalActionsProps {
  feature: FeatureData
  onRefresh: () => void
  onExport: () => void
}

function ModalActions({ feature, onRefresh, onExport }: ModalActionsProps): JSX.Element {
  const isDone = feature.state === 'DONE'
  return (
    <div className={styles.mActions}>
      <button type="button" className={styles.actionBtn} onClick={onRefresh}>↻ Refresh</button>
      <button type="button" className={styles.actionBtn} disabled>⇅ Run Migration</button>
      <button type="button" className={styles.actionBtn} onClick={onExport}>↓ Export JSON</button>
      <span className={styles.mStatus}>
        <i className={styles.mStatusDot} {...(isDone ? {} : { 'data-running': '' })} />
        {isDone ? 'runner: finished' : 'runner: running'}
        {' · '}{feature.tokens} tok{' · '}{feature.cost}
      </span>
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
          {tab.count !== undefined && <span className={styles.ct}>{tab.count}</span>}
        </button>
      ))}
    </div>
  )
}
