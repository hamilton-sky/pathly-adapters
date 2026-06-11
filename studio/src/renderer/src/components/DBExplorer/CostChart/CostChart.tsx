import { useState, useEffect, useRef, useCallback } from 'react'
import { CostBars } from './CostBars'
import styles from './CostChart.module.css'

interface TrendPoint {
  day: string
  cost_usd: number
  tokens_in: number
  tokens_out: number
  span_count: number
}

function bucketToPoint(b: DailyTrendBucket): TrendPoint {
  return {
    day: b.bucket,
    cost_usd: b.cost_usd_reported,
    tokens_in: b.input_tokens,
    tokens_out: 0,
    span_count: b.count,
  }
}

interface TooltipState {
  point: TrendPoint
  svgX: number   // relative X inside the SVG element (0-560)
}

function fmtCost(n: number): string {
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}

function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

interface TooltipProps {
  tip: TooltipState
  containerWidth: number
}

function Tooltip({ tip, containerWidth }: TooltipProps): JSX.Element {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    // Map SVgX (0-560) to container pixels, then clamp so tooltip stays visible
    const px = (tip.svgX / 560) * containerWidth
    const clamped = Math.min(Math.max(px, 60), containerWidth - 60)
    el.style.setProperty('--tip-x', `${clamped}px`)
  }, [tip.svgX, containerWidth])

  return (
    <div ref={ref} className={styles.tooltip} role="tooltip">
      <span className={styles.tipDay}>{tip.point.day}</span>
      <span className={styles.tipCost}>{fmtCost(tip.point.cost_usd)}</span>
      <span className={styles.tipMeta}>
        {fmtTokens(tip.point.tokens_in + tip.point.tokens_out)} tok
        {' · '}
        {tip.point.span_count} span{tip.point.span_count !== 1 ? 's' : ''}
      </span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface CostChartProps {
  featureName: string
}

export function CostChart({ featureName }: CostChartProps): JSX.Element {
  const [points, setPoints]  = useState<TrendPoint[]>([])
  const [days, setDays]      = useState<30 | 14 | 7>(30)
  const [tip, setTip]        = useState<TooltipState | null>(null)
  const [loading, setLoading] = useState(true)
  const containerRef          = useRef<HTMLDivElement>(null)
  const [containerW, setContainerW] = useState(560)

  useEffect(() => {
    if (!containerRef.current) return
    const obs = new ResizeObserver(([e]) => setContainerW(e.contentRect.width))
    obs.observe(containerRef.current)
    return () => obs.disconnect()
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await window.pathly.db.trends(featureName, days)
      const raw = data?.trends ?? []
      setPoints(raw.map(bucketToPoint))
    } catch {
      setPoints([])
    } finally {
      setLoading(false)
    }
  }, [featureName, days])

  useEffect(() => { load() }, [load])

  const totalCost = points.reduce((s, p) => s + p.cost_usd, 0)
  const totalSpans = points.reduce((s, p) => s + p.span_count, 0)

  const handleHover = useCallback((p: TrendPoint | null, svgX: number) => {
    setTip(p ? { point: p, svgX } : null)
  }, [])

  return (
    <div className={styles.wrapper}>
      <div className={styles.head}>
        <div className={styles.headLeft}>
          <span className={styles.title}>Cost over time</span>
          {!loading && totalSpans > 0 && (
            <span className={styles.meta}>
              {fmtCost(totalCost)} · {totalSpans} spans
            </span>
          )}
        </div>
        <div className={styles.rangeGroup} role="group" aria-label="Time range">
          {([7, 14, 30] as const).map((d) => (
            <button
              key={d}
              type="button"
              className={styles.rangeBtn}
              {...(days === d ? { 'data-active': '' } : {})}
              onClick={() => setDays(d)}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div ref={containerRef} className={styles.chartArea}>
        {loading && <div className={styles.empty}>Loading…</div>}
        {!loading && points.length === 0 && (
          <div className={styles.empty}>
            No span data yet — run agents to populate cost history.
          </div>
        )}
        {!loading && points.length > 0 && (
          <>
            <CostBars points={points} onHover={handleHover} />
            {tip && <Tooltip tip={tip} containerWidth={containerW} />}
          </>
        )}
      </div>
    </div>
  )
}
