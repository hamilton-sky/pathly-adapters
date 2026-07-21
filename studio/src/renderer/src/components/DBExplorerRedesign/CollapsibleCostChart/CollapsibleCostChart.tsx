import { useState } from 'react'
import { SegmentedToggle } from '../SegmentedToggle'
import styles from './CollapsibleCostChart.module.css'

type ScopeMode = 'project' | 'global'
type RangeDays = 7 | 14 | 30
type ScaleMode = 'linear' | 'log'

interface CollapsibleCostChartProps {
  /** Contiguous daily cost, oldest → newest (gap-filled by the caller). */
  series: number[]
  startDate: Date
  /** Index of the peak bar (−1 when all zero). */
  peakIndex: number
  /** Summary numbers shown in the always-visible header. */
  total: string
  avgPerActiveDay: string
  peak: string
  peakDay: string
  spanCount: number
  /** Controlled data scope + range — the parent refetches on change. */
  scope: ScopeMode
  onScope: (s: ScopeMode) => void
  range: RangeDays
  onRange: (r: RangeDays) => void
  loading?: boolean
  /** Collapsed by default per product decision. */
  defaultOpen?: boolean
}

const SCOPE_OPTIONS: { label: string; value: ScopeMode }[] = [
  { label: 'Project', value: 'project' },
  { label: 'Global', value: 'global' },
]
const RANGE_OPTIONS: { label: string; value: RangeDays }[] = [
  { label: '7d', value: 7 },
  { label: '14d', value: 14 },
  { label: '30d', value: 30 },
]
const SCALE_OPTIONS: { label: string; value: ScaleMode }[] = [
  { label: 'Linear', value: 'linear' },
  { label: 'Log', value: 'log' },
]
const GRID_FRACS = [1, 0.66, 0.33, 0]

function fmtDay(d: Date): string {
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

function dateAt(start: Date, i: number): Date {
  const d = new Date(start)
  d.setDate(start.getDate() + i)
  return d
}

function barHeight(v: number, max: number, scale: ScaleMode): number {
  if (v <= 0) return 0
  if (scale === 'log') {
    return Math.max((Math.log10(v + 1) / Math.log10(max + 1)) * 100, 2)
  }
  return Math.max((v / max) * 100, 2)
}

/**
 * Cost-over-time bar chart that collapses to just its summary numbers. The
 * header (title + total/avg/peak) is always visible; the plot and the
 * scope/range/scale switches only mount when expanded. Scope + range are
 * controlled (the parent refetches); scale is a pure presentation toggle.
 */
export function CollapsibleCostChart({
  series,
  startDate,
  peakIndex,
  total,
  avgPerActiveDay,
  peak,
  peakDay,
  spanCount,
  scope,
  onScope,
  range,
  onRange,
  loading = false,
  defaultOpen = false,
}: CollapsibleCostChartProps): JSX.Element {
  const [open, setOpen] = useState(defaultOpen)
  const [scale, setScale] = useState<ScaleMode>('linear')
  const [hover, setHover] = useState<number | null>(null)

  const max = Math.max(...series, 0.001)
  const n = series.length
  const hoverH = hover !== null ? barHeight(series[hover], max, scale) : 0
  // Clamp the tooltip's horizontal centre so the edge bars (esp. the peak) don't
  // render half-off the plot.
  const tipLeft = hover !== null ? Math.min(94, Math.max(6, ((hover + 0.5) / n) * 100)) : 50

  return (
    <div className={styles.card}>
      <div className={styles.head} data-open={open ? '' : undefined}>
        <div className={styles.left}>
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setOpen((v) => !v)}
            {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          >
            <span className={styles.chevron} data-open={open ? '' : undefined}>▸</span>
            <span className={styles.title}>Cost over time</span>
            {loading && <span className={styles.loadingTag}>refreshing…</span>}
          </button>
          <div className={styles.stats}>
            <Summary value={total} label={`total · ${spanCount} spans`} tone="green" />
            <Summary value={avgPerActiveDay} label="avg / active day" />
            <Summary value={peak} label={`peak · ${peakDay}`} tone="teal" />
          </div>
        </div>
        {open && (
          <div className={styles.toggles}>
            <SegmentedToggle options={SCOPE_OPTIONS} value={scope} onChange={onScope} ariaLabel="Data scope" />
            <SegmentedToggle options={RANGE_OPTIONS} value={range} onChange={onRange} ariaLabel="Time range" />
            <SegmentedToggle options={SCALE_OPTIONS} value={scale} onChange={setScale} ariaLabel="Value scale" />
          </div>
        )}
      </div>

      {open && (
        <div className={styles.plot}>
          <div className={styles.yAxis}>
            {GRID_FRACS.map((f) => (
              <div key={f} className={styles.yLabel} style={{ ['--pos' as string]: `${f * 100}%` } as React.CSSProperties}>
                {f === 0 ? '$0' : `$${(f * max).toFixed(2)}`}
              </div>
            ))}
          </div>
          <div className={styles.body}>
            <div className={styles.canvas}>
              {GRID_FRACS.map((f) => (
                <div
                  key={f}
                  className={styles.gridLine}
                  style={{ ['--pos' as string]: `${f * 100}%` } as React.CSSProperties}
                  {...(f === 0 ? { 'data-base': '' } : {})}
                />
              ))}
              <div className={styles.bars}>
                {series.map((v, i) => {
                  const isZero = v <= 0
                  const isPeak = i === peakIndex
                  const h = barHeight(v, max, scale)
                  return (
                    <div
                      key={i}
                      className={styles.col}
                      onMouseEnter={() => setHover(i)}
                      onMouseLeave={() => setHover((cur) => (cur === i ? null : cur))}
                    >
                      <div
                        className={styles.bar}
                        style={{ ['--bar-h' as string]: `${h}%`, ['--bar-delay' as string]: `${i * 0.012}s` } as React.CSSProperties}
                        {...(isPeak ? { 'data-peak': '' } : {})}
                        {...(isZero ? { 'data-zero': '' } : {})}
                        {...(hover === i ? { 'data-hover': '' } : {})}
                      />
                      {isPeak && hover === null && <div className={styles.peakTag}>{peak}</div>}
                    </div>
                  )
                })}
              </div>
              {hover !== null && (
                <div
                  className={styles.tooltip}
                  style={{ ['--left' as string]: `${tipLeft}%`, ['--bottom' as string]: `${hoverH}%` } as React.CSSProperties}
                >
                  <span className={styles.tipDay}>{fmtDay(dateAt(startDate, hover))}</span>
                  <span className={styles.tipCost}>${series[hover].toFixed(2)}</span>
                </div>
              )}
            </div>
            <div className={styles.xAxis}>
              {series.map((_, i) => {
                const d = new Date(startDate)
                d.setDate(startDate.getDate() + i)
                const show = i % 5 === 0 || i === n - 1
                return (
                  <div key={i} className={styles.xCell}>
                    {show && <span className={styles.xLabel}>{fmtDay(d)}</span>}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Summary({ value, label, tone }: { value: string; label: string; tone?: 'green' | 'teal' }): JSX.Element {
  return (
    <div className={styles.summary}>
      <span className={styles.summaryValue} data-tone={tone}>{value}</span>
      <span className={styles.summaryLabel}>{label}</span>
    </div>
  )
}
