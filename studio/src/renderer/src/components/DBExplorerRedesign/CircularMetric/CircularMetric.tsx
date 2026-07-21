import type { MetricKey } from '../types'
import { SegmentedToggle } from '../SegmentedToggle'
import { computeMetric, toDonut, type MetricInputs } from '../metricUtils'
import styles from './CircularMetric.module.css'

interface CircularMetricProps {
  inputs: MetricInputs
  metric: MetricKey
  onMetric: (m: MetricKey) => void
}

const METRIC_OPTIONS: { label: string; value: MetricKey; title: string }[] = [
  { label: '◷', value: 'state', title: 'Cost by pipeline state' },
  { label: '◔', value: 'agent', title: 'Agent cost share' },
  { label: '◑', value: 'tokens', title: 'Token usage split' },
  { label: '◕', value: 'status', title: 'Feature status' },
]

/**
 * Mixpanel-style donut. A single conic-gradient ring with a hole; the segmented
 * control swaps between four live aggregations of the panel's feature/token/agent
 * data. Gradient + swatch colours are theme tokens injected via CSS custom
 * properties, so the ring inherits the active theme.
 */
export function CircularMetric({ inputs, metric, onMetric }: CircularMetricProps): JSX.Element {
  const result = computeMetric(metric, inputs)
  const { gradient, legend } = toDonut(result)

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.title}>{result.title}</span>
        <SegmentedToggle options={METRIC_OPTIONS} value={metric} onChange={onMetric} ariaLabel="Metric" />
      </div>
      <div className={styles.body}>
        <div className={styles.donut}>
          <div className={styles.ring} style={{ ['--donut-gradient' as string]: gradient } as React.CSSProperties} />
          <div className={styles.hole}>
            <span className={styles.center}>{result.center}</span>
            <span className={styles.centerLabel}>{result.centerLabel}</span>
          </div>
        </div>
        <div className={styles.legend}>
          {result.pending && <span className={styles.hint}>Loading…</span>}
          {!result.pending && legend.length === 0 && <span className={styles.hint}>No data</span>}
          {legend.map((l) => (
            <div key={l.label} className={styles.row}>
              <span className={styles.swatch} style={{ ['--swatch' as string]: l.color } as React.CSSProperties} />
              <span className={styles.label}>{l.label}</span>
              <span className={styles.value}>{l.value}</span>
              <span className={styles.pct}>{l.pct}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
