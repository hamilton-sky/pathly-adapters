import { SummaryStat } from './SummaryStat'
import { SegmentedToggle } from './SegmentedToggle'
import { fmtCost } from './chartMath'
import type { RangeDays, ScaleMode } from './types'
import styles from './ChartHeader.module.css'

interface ChartHeaderProps {
  total: number
  totalSpans: number
  avgPerActiveDay: number
  peakCost: number
  peakDay: string
  range: RangeDays
  onRange: (r: RangeDays) => void
  scale: ScaleMode
  onScale: (s: ScaleMode) => void
}

const RANGE_OPTIONS: { label: string; value: RangeDays }[] = [
  { label: '7d', value: 7 },
  { label: '14d', value: 14 },
  { label: '30d', value: 30 },
]

const SCALE_OPTIONS: { label: string; value: ScaleMode }[] = [
  { label: 'Linear', value: 'linear' },
  { label: 'Log', value: 'log' },
]

/** Title, summary metrics, and the range / scale switches. */
export function ChartHeader({
  total,
  totalSpans,
  avgPerActiveDay,
  peakCost,
  peakDay,
  range,
  onRange,
  scale,
  onScale,
}: ChartHeaderProps): JSX.Element {
  return (
    <div className={styles.head}>
      <div className={styles.left}>
        <span className={styles.title}>Cost over time</span>
        <div className={styles.stats}>
          <SummaryStat value={fmtCost(total)} label={`total · ${totalSpans} spans`} tone="green" />
          <SummaryStat value={fmtCost(avgPerActiveDay)} label="avg / active day" />
          <SummaryStat value={fmtCost(peakCost)} label={`peak · ${peakDay}`} tone="teal" />
        </div>
      </div>
      <div className={styles.toggles}>
        <SegmentedToggle options={RANGE_OPTIONS} value={range} onChange={onRange} ariaLabel="Time range" />
        <SegmentedToggle options={SCALE_OPTIONS} value={scale} onChange={onScale} ariaLabel="Value scale" />
      </div>
    </div>
  )
}
