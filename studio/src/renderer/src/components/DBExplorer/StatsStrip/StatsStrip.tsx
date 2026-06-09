import type { FeatureData } from '../dbExplorerData'
import styles from './StatsStrip.module.css'

interface StatsStripProps {
  stats: DbStats | null
  features: FeatureData[]
}

export function StatsStrip({ stats, features }: StatsStripProps): JSX.Element {
  const featureCount = stats?.features ?? features.length
  const eventCount = stats?.events ?? features.reduce((s, f) => s + f.events, 0)
  const invCount = stats?.invocations ?? features.reduce((s, f) => s + f.inv, 0)
  const tokenCount = stats?.total_tokens ?? features.reduce((s, f) => s + parseInt(f.tokens.replace(/,/g, ''), 10), 0)
  const costVal = stats?.total_cost_usd ?? features.reduce((s, f) => s + parseFloat(f.cost.replace('$', '')), 0)

  return (
    <div className={styles.stats}>
      <div className={styles.stat}>
        <div className={styles.k}>Features</div>
        <div className={styles.v}>{featureCount}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Events</div>
        <div className={styles.v}>{eventCount}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Invocations</div>
        <div className={styles.v}>{invCount}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Tokens</div>
        <div className={styles.v}>{tokenCount.toLocaleString()}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Cost</div>
        <div className={`${styles.v} ${styles.cost}`}>${costVal.toFixed(2)}</div>
      </div>
    </div>
  )
}
