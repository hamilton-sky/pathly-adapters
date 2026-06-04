import React from 'react'
import { Tooltip } from '../ui/Tooltip'
import { useAgentTelemetry, fmtTokens, fmtWall, fmtCost, EMPTY_TOOLTIP } from './utils'
import styles from './Monitor.module.css'

export function MetricsStrip(): JSX.Element {
  const { totalTokens, lastWall, totalCost, noTelemetry, eventsCount, hasTelemetry } = useAgentTelemetry()

  const billingPending = hasTelemetry && totalCost === 0
  const costValue = billingPending ? '$…' : fmtCost(totalCost)
  const costEmpty = !billingPending && totalCost === 0
  const costTooltip = billingPending
    ? 'Billing pending — BILLING_UPDATE will reconcile when agent session closes'
    : EMPTY_TOOLTIP

  const tiles: { label: string; value: string; empty: boolean; tooltip?: string }[] = [
    { label: 'TOKENS', value: fmtTokens(totalTokens), empty: totalTokens === 0, tooltip: EMPTY_TOOLTIP },
    { label: 'WALL',   value: fmtWall(lastWall),      empty: lastWall == null,  tooltip: EMPTY_TOOLTIP },
    { label: 'COST',   value: costValue,               empty: costEmpty,         tooltip: costTooltip },
    { label: 'EVENTS', value: String(eventsCount),    empty: false },
  ]

  return (
    <div className={styles.metricsRoot}>
      <div className={styles.metricsRow}>
        {tiles.map((tile) => (
          <Tooltip
            key={tile.label}
            label={tile.empty && tile.tooltip ? tile.tooltip : tile.label}
            placement="top"
            delay={300}
          >
            <div className={styles.metricsTile}>
              <span className={`${styles.metricsValue} ${tile.empty ? styles.metricsValueEmpty : styles.metricsValueFull}`}>
                {tile.value}
              </span>
              <span className={styles.metricsLabel}>{tile.label}</span>
            </div>
          </Tooltip>
        ))}
      </div>
      {noTelemetry && (
        <div className={styles.metricsNoTelemetry}>
          No telemetry captured — HTTP pipeline events do not include cost data
        </div>
      )}
    </div>
  )
}
