import { CostTooltip } from './CostTooltip'
import { heightFrac, gridValue, fmtCost, fmtDay } from './chartMath'
import type { CostPoint, ScaleMode } from './types'
import styles from './CostBars.module.css'

interface CostBarsProps {
  points: CostPoint[]
  scale: ScaleMode
  hoverIndex: number | null
  onHover: (index: number | null) => void
}

const GRID_FRACS = [1, 0.66, 0.33, 0]

/** The plot itself: y-axis, gridlines, bars, x-axis, hover guide + tooltip. */
export function CostBars({ points, scale, hoverIndex, onHover }: CostBarsProps): JSX.Element {
  const n = points.length
  const max = Math.max(...points.map((p) => p.cost_usd), 0.001)
  const labelEvery = Math.ceil(n / 7)
  const gap = n > 20 ? 3 : n > 10 ? 6 : 12
  const barMaxWidth = n > 14 ? 22 : 40
  const peakIndex = points.reduce((mi, p, i) => (p.cost_usd > points[mi].cost_usd ? i : mi), 0)

  const hovered = hoverIndex != null ? points[hoverIndex] : null
  const guideLeft = n > 1 && hoverIndex != null ? (hoverIndex / (n - 1)) * 100 : 50
  const tipLeft = Math.min(Math.max(guideLeft, 12), 88)

  return (
    <div className={styles.plot}>
      <div className={styles.yAxis}>
        {GRID_FRACS.map((f) => (
          <div key={f} className={styles.yLabel} style={{ bottom: `${f * 100}%` }}>
            {f === 0 ? '$0' : fmtCost(gridValue(f, max, scale))}
          </div>
        ))}
      </div>

      <div className={styles.body}>
        <div className={styles.canvas} onMouseLeave={() => onHover(null)}>
          {GRID_FRACS.map((f) => (
            <div
              key={f}
              className={styles.gridLine}
              style={{ bottom: `${f * 100}%` }}
              {...(f === 0 ? { 'data-base': '' } : {})}
            />
          ))}

          {hovered && hoverIndex != null && (
            <>
              <div className={styles.guide} style={{ left: `${guideLeft}%` }} />
              <CostTooltip point={hovered} leftPct={tipLeft} />
            </>
          )}

          <div
            className={styles.bars}
            style={{ gap: `${gap}px` }}
            {...(hoverIndex != null ? { 'data-hovering': '' } : {})}
          >
            {points.map((p, i) => {
              const isZero = p.cost_usd <= 0
              const isPeak = i === peakIndex && p.cost_usd > 0
              const h = Math.max(heightFrac(p.cost_usd, max, scale) * 100, isZero ? 0 : 2)
              return (
                <div key={p.day} className={styles.col} onMouseEnter={() => onHover(i)}>
                  <div
                    className={styles.bar}
                    style={{
                      height: `${h}%`,
                      maxWidth: `${barMaxWidth}px`,
                      minHeight: isZero ? 0 : 3,
                      animationDelay: `${i * 0.012}s`,
                    }}
                    {...(isPeak ? { 'data-peak': '' } : {})}
                    {...(isZero ? { 'data-zero': '' } : {})}
                  />
                  {isPeak && <div className={styles.peakTag}>{fmtCost(p.cost_usd)}</div>}
                </div>
              )
            })}
          </div>
        </div>

        <div className={styles.xAxis} style={{ gap: `${gap}px` }}>
          {points.map((p, i) => (
            <div key={p.day} className={styles.xCell}>
              {(i % labelEvery === 0 || i === n - 1) && (
                <span className={styles.xLabel}>{fmtDay(p.day)}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
