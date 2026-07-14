import { useMemo, useState } from 'react'
import { ChartHeader } from './ChartHeader'
import { CostBars } from './CostBars'
import type { CostPoint, RangeDays, ScaleMode, ScopeMode } from './types'
import styles from './CostOverTimeChart.module.css'

interface CostOverTimeChartProps {
  /** Daily points, oldest → newest. Length may exceed the selected range. */
  points: CostPoint[]
  /** Initial range in days. Default 30. */
  defaultRange?: RangeDays
  /** Initial scale. Default 'linear'. */
  defaultScale?: ScaleMode
  /** While true and no points are loaded yet, show a loading placeholder. */
  loading?: boolean
  /** When provided, render a Project/Global data-scope switch in the header. */
  scope?: ScopeMode
  onScope?: (s: ScopeMode) => void
}

/**
 * Cost-over-time bar chart: value scale + gridlines, peak marker, in-bounds
 * hover tooltip, and range (7/14/30d) + scale (linear/log) switches.
 *
 * State lives here; presentation is delegated to <ChartHeader> and <CostBars>.
 */
export function CostOverTimeChart({
  points,
  defaultRange = 30,
  defaultScale = 'linear',
  loading = false,
  scope,
  onScope,
}: CostOverTimeChartProps): JSX.Element {
  const [range, setRange] = useState<RangeDays>(defaultRange)
  const [scale, setScale] = useState<ScaleMode>(defaultScale)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const view = useMemo(() => points.slice(-range), [points, range])

  const summary = useMemo(() => {
    const total = view.reduce((s, p) => s + p.cost_usd, 0)
    const totalSpans = view.reduce((s, p) => s + p.span_count, 0)
    const active = view.filter((p) => p.cost_usd > 0).length || 1
    const peak = view.reduce<CostPoint>(
      (m, p) => (p.cost_usd > m.cost_usd ? p : m),
      view[0] ?? { day: '', cost_usd: 0, tokens: 0, span_count: 0 },
    )
    return {
      total,
      totalSpans,
      avgPerActiveDay: total / active,
      peakCost: peak.cost_usd,
      peakDay: peak.day.length >= 10 ? peak.day.slice(5).replace('-', '/') : peak.day,
    }
  }, [view])

  const handleRange = (r: RangeDays): void => {
    setRange(r)
    setHoverIndex(null)
  }

  return (
    <div className={styles.card}>
      <ChartHeader
        total={summary.total}
        totalSpans={summary.totalSpans}
        avgPerActiveDay={summary.avgPerActiveDay}
        peakCost={summary.peakCost}
        peakDay={summary.peakDay}
        range={range}
        onRange={handleRange}
        scale={scale}
        onScale={setScale}
        scope={scope}
        onScope={onScope}
      />
      {view.length > 0 ? (
        <CostBars points={view} scale={scale} hoverIndex={hoverIndex} onHover={setHoverIndex} />
      ) : loading ? (
        <div className={styles.empty}>Loading…</div>
      ) : (
        <div className={styles.empty}>No span data yet — run agents to populate cost history.</div>
      )}
    </div>
  )
}
