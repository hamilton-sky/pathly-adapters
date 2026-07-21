import { useState } from 'react'
import type { FeatureData } from '../types'
import { StatePill } from '../StatePill'
import { TimelineTab } from '../../DBExplorer/TimelineTab'
import { EventsTab } from '../../DBExplorer/EventsTab'
import { AgentsTab } from '../../DBExplorer/AgentsTab'
import { TracesTab } from '../../DBExplorer/TracesTab'
import { InspectTab } from '../../DBExplorer/InspectTab'
import { TrendsTab } from '../../DBExplorer/TrendsTab/TrendsTab'
import { useFeatureDetail } from './hooks/useFeatureDetail'
import styles from './FeatureDetailPage.module.css'

type TabId = 'timeline' | 'events' | 'agents' | 'traces' | 'inspect' | 'trends'

interface FeatureDetailPageProps {
  feature: FeatureData
  onBack: () => void
}

function exportJson(feature: FeatureData, transitions: unknown, events: unknown): void {
  const payload = { feature, transitions, events }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${feature.name}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Full-page feature view (replaces the old FeatureModal). Keeps the redesign's
 * page shell — header / big-stats / tab bar — but fetches live detail data via
 * useFeatureDetail and renders the shipped live tab components for the bodies:
 * Timeline / Events / Agents / Traces / Inspect / Trends.
 */
export function FeatureDetailPage({ feature, onBack }: FeatureDetailPageProps): JSX.Element {
  const [tab, setTab] = useState<TabId>('timeline')
  const { transitions, rawEvents, otelSpans, pricingTable, loading, refresh } = useFeatureDetail(feature)

  const agentCount = rawEvents.filter((e) => e.event_type === 'AGENT_DONE').length
  const isDone = feature.state === 'DONE'

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'timeline', label: 'Timeline', count: transitions.length || undefined },
    { id: 'events', label: 'Events', count: rawEvents.length || undefined },
    { id: 'agents', label: 'Agents', count: agentCount || undefined },
    { id: 'traces', label: 'Traces', count: otelSpans.length || undefined },
    { id: 'inspect', label: 'Inspect' },
    { id: 'trends', label: 'Trends' },
  ]

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <button type="button" className={styles.back} onClick={onBack}>← DB Explorer</button>
        <div className={styles.headRow}>
          <h2 className={styles.name}>{feature.name}</h2>
          <StatePill state={feature.state} large />
          <span className={styles.runner}>
            <i className={styles.runnerDot} {...(isDone ? {} : { 'data-running': '' })} />
            {isDone ? 'runner: finished' : 'runner: running'}
          </span>
          <div className={styles.spacer} />
          <button type="button" className={styles.action} onClick={refresh}>↻ Refresh</button>
          <button type="button" className={styles.action} onClick={() => exportJson(feature, transitions, rawEvents)}>↓ Export JSON</button>
        </div>
      </div>

      <div className={styles.bigStats}>
        <BigStat k="Events" v={feature.events} />
        <BigStat k="Invocations" v={feature.inv} />
        <BigStat k="Tokens" v={feature.tokens} />
        <BigStat k="Cost" v={feature.cost} cost />
      </div>

      <div className={styles.tabs}>
        {tabs.map((t) => (
          <button key={t.id} type="button" className={styles.tab} {...(tab === t.id ? { 'data-active': '' } : {})} onClick={() => setTab(t.id)}>
            {t.label}
            {t.count !== undefined && <span className={styles.count}>{t.count}</span>}
          </button>
        ))}
      </div>

      <div className={styles.body}>
        {loading
          ? <div className={styles.empty}>Loading…</div>
          : <>
              {tab === 'timeline' && <TimelineTab transitions={transitions} />}
              {tab === 'events' && <EventsTab events={rawEvents} />}
              {tab === 'agents' && <AgentsTab events={rawEvents} pricingTable={pricingTable} />}
              {tab === 'traces' && <TracesTab spans={otelSpans} />}
              {tab === 'inspect' && <InspectTab events={rawEvents} pricingTable={pricingTable} />}
              {tab === 'trends' && <TrendsTab featureName={feature.name} events={rawEvents} pricingTable={pricingTable} />}
            </>
        }
      </div>
    </div>
  )
}

function BigStat({ k, v, cost = false }: { k: string; v: string | number; cost?: boolean }): JSX.Element {
  return (
    <div className={styles.bigStat}>
      <div className={styles.bsk}>{k}</div>
      <div className={`${styles.bsv} ${cost ? styles.cost : ''}`}>{v}</div>
    </div>
  )
}
