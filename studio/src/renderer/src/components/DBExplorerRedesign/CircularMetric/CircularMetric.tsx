import { useState } from 'react'
import type { MetricKey } from '../types'
import { SegmentedToggle } from '../SegmentedToggle'
import { computeMetric, type MetricInputs } from '../metricUtils'
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

const R = 47
const CIRC = 2 * Math.PI * R

/**
 * Mixpanel-style donut. An SVG ring whose arc segments are individually
 * hoverable; hovering a slice (or its legend row) highlights it and swaps the
 * centre to show that slice's value + share. Four live aggregations of the
 * panel's feature/token/agent data; colours are theme tokens.
 */
export function CircularMetric({ inputs, metric, onMetric }: CircularMetricProps): JSX.Element {
  const [hoverSeg, setHoverSeg] = useState<number | null>(null)
  const result = computeMetric(metric, inputs)
  const total = result.total || 1

  let cum = 0
  const arcs = result.segs.map((s, i) => {
    const frac = s.value / total
    const arc = {
      i,
      label: s.label,
      color: s.color,
      dash: frac * CIRC,
      gap: CIRC - frac * CIRC,
      offset: -cum * CIRC,
      pct: Math.round(frac * 100),
      valueFmt: result.fmt(s.value),
    }
    cum += frac
    return arc
  })

  const active = hoverSeg !== null ? arcs[hoverSeg] : undefined
  const centerValue = active ? active.valueFmt : result.center
  const centerLabel = active ? `${active.label} · ${active.pct}%` : result.centerLabel
  const enter = (i: number): void => setHoverSeg(i)
  const leave = (i: number): void => setHoverSeg((cur) => (cur === i ? null : cur))

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <span className={styles.title}>{result.title}</span>
        <SegmentedToggle options={METRIC_OPTIONS} value={metric} onChange={onMetric} ariaLabel="Metric" />
      </div>
      <div className={styles.body}>
        <div className={styles.donut}>
          <svg viewBox="0 0 120 120" className={styles.svg} {...(hoverSeg !== null ? { 'data-hovering': '' } : {})} role="img" aria-label={result.title}>
            <g transform="rotate(-90 60 60)">
              {arcs.length === 0 ? (
                <circle cx="60" cy="60" r={R} className={styles.arcEmpty} />
              ) : (
                arcs.map((a) => (
                  <circle
                    key={a.label}
                    cx="60"
                    cy="60"
                    r={R}
                    className={styles.arc}
                    {...(hoverSeg === a.i ? { 'data-active': '' } : {})}
                    style={{ ['--seg-color' as string]: a.color, ['--dash' as string]: a.dash, ['--gap' as string]: a.gap, ['--offset' as string]: a.offset } as React.CSSProperties}
                    onMouseEnter={() => enter(a.i)}
                    onMouseLeave={() => leave(a.i)}
                  />
                ))
              )}
            </g>
          </svg>
          <div className={styles.hole}>
            <span className={styles.center}>{centerValue}</span>
            <span className={styles.centerLabel}>{centerLabel}</span>
          </div>
        </div>
        <div className={styles.legend}>
          {result.pending && <span className={styles.hint}>Loading…</span>}
          {!result.pending && arcs.length === 0 && <span className={styles.hint}>No data</span>}
          {arcs.map((a) => (
            <div
              key={a.label}
              className={styles.row}
              {...(hoverSeg === a.i ? { 'data-active': '' } : {})}
              onMouseEnter={() => enter(a.i)}
              onMouseLeave={() => leave(a.i)}
            >
              <span className={styles.swatch} style={{ ['--swatch' as string]: a.color } as React.CSSProperties} />
              <span className={styles.label}>{a.label}</span>
              <span className={styles.value}>{a.valueFmt}</span>
              <span className={styles.pct}>{a.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
