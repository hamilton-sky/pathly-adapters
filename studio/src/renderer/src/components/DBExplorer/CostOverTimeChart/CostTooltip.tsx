import { fmtCost, fmtTokens, fmtDay } from './chartMath'
import type { CostPoint } from './types'
import styles from './CostTooltip.module.css'

interface CostTooltipProps {
  point: CostPoint
  /** Horizontal position (0..100) — already clamped by the caller. */
  leftPct: number
}

/** Floating readout for the hovered bar. Kept inside the plot bounds. */
export function CostTooltip({ point, leftPct }: CostTooltipProps): JSX.Element {
  return (
    <div className={styles.tooltip} style={{ left: `${leftPct}%` }} role="tooltip">
      <div className={styles.day}>{fmtDay(point.day)}</div>
      <div className={styles.cost}>{fmtCost(point.cost_usd)}</div>
      <div className={styles.meta}>
        {fmtTokens(point.tokens)} tok · {point.span_count} span{point.span_count !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
