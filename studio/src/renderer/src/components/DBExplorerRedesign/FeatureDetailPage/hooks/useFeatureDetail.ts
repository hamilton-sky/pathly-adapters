import { useState, useEffect, useCallback } from 'react'
import type { FeatureData } from '../../types'
import type { TransitionData } from '../../../DBExplorer/dbExplorerData'
import { fetchPricingTable, type PricingTable } from '../../../DBExplorer/costUtils'

interface FeatureDetailData {
  transitions: TransitionData[]
  rawEvents: DbEvent[]
  otelSpans: DbOtelSpan[]
}

const EMPTY: FeatureDetailData = { transitions: [], rawEvents: [], otelSpans: [] }

function calcDuration(from: string, to: string): string {
  const diff = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000)
  if (diff <= 0) return '—'
  const m = Math.floor(diff / 60)
  return m > 0 ? `${m}m ${diff % 60}s` : `${diff}s`
}

/**
 * Derive the timeline from the raw event stream. Oldest→newest so the flow reads
 * forward, and each state's `duration` measures the gap to the NEXT state.
 */
export function eventsToTransitions(events: DbEvent[]): TransitionData[] {
  const stateEvents = events
    .filter((e) => e.event_type === 'STATE_TRANSITION')
    .slice()
    .sort((a, b) => a.ts.localeCompare(b.ts))
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

export interface UseFeatureDetail extends FeatureDetailData {
  pricingTable: PricingTable | null
  loading: boolean
  refresh: () => void
}

/**
 * Fetches a feature's live detail data (events + otel + pricing), derives the
 * timeline, and live-refreshes every 4s while the run is active. Reproduces the
 * data block the old FeatureModal owned so the redesigned detail page can reuse
 * the shipped live tab components.
 */
export function useFeatureDetail(feature: FeatureData | null): UseFeatureDetail {
  const [data, setData] = useState<FeatureDetailData>(EMPTY)
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

  // Live-refresh while the run is active so late BILLING_UPDATE / AGENT_DONE
  // events (especially codex cost, which lands after the agent exits) appear
  // without a manual Refresh. Stops once the run reports DONE.
  useEffect(() => {
    if (!feature || feature.state === 'DONE') return
    const id = setInterval(() => setRefreshKey((k) => k + 1), 4000)
    return () => clearInterval(id)
  }, [feature?.name, feature?.state])

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), [])

  return { ...data, pricingTable, loading, refresh }
}
