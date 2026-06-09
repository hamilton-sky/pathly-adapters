/**
 * CostBars — pure SVG bar chart rendering.
 * Receives pre-computed layout values so it stays stateless.
 */

import styles from './CostChart.module.css'

const W = 560
const H_INNER = 80   // bar area height
const H_LABEL = 18   // date label row height
const H_TOTAL = H_INNER + H_LABEL
const BAR_GAP = 3
const MIN_BAR_H = 3  // always show a stub so zero-cost days are visible

interface CostBarsProps {
  points: DbTrendPoint[]
  onHover: (p: DbTrendPoint | null, svgX: number) => void
}

function fmtDay(day: string): string {
  // "2026-06-09" → "06/09"
  return day.length >= 10 ? day.slice(5).replace('-', '/') : day
}

export function CostBars({ points, onHover }: CostBarsProps): JSX.Element {
  if (points.length === 0) return <></>

  const n      = points.length
  const barW   = Math.max(4, (W - (n - 1) * BAR_GAP) / n)
  const maxCost = Math.max(...points.map((p) => p.cost_usd), 0.001)
  // Label every Nth bar so they don't overlap; always include last
  const labelEvery = Math.ceil(n / 7)

  return (
    <svg
      viewBox={`0 0 ${W} ${H_TOTAL}`}
      preserveAspectRatio="none"
      className={styles.svg}
      aria-label="Cost over time bar chart"
      role="img"
    >
      {points.map((p, i) => {
        const barH = p.cost_usd > 0
          ? Math.max(MIN_BAR_H, (p.cost_usd / maxCost) * H_INNER)
          : MIN_BAR_H
        const x  = i * (barW + BAR_GAP)
        const y  = H_INNER - barH
        const showLabel = i % labelEvery === 0 || i === n - 1

        return (
          <g
            key={p.day}
            onMouseEnter={() => onHover(p, x + barW / 2)}
            onMouseLeave={() => onHover(null, 0)}
          >
            <rect
              x={x} y={y}
              width={barW} height={barH}
              rx={2}
              className={p.cost_usd > 0 ? styles.bar : styles.barEmpty}
            />
            {showLabel && (
              <text
                x={x + barW / 2}
                y={H_TOTAL - 2}
                textAnchor="middle"
                className={styles.axisLabel}
              >
                {fmtDay(p.day)}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
