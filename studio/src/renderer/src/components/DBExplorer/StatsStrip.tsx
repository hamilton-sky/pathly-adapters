import { FEATURES } from './dbExplorerData'
import styles from './StatsStrip.module.css'

function totalEvents(): number {
  return FEATURES.reduce((sum, f) => sum + f.events, 0)
}

function totalInvocations(): number {
  return FEATURES.reduce((sum, f) => sum + f.inv, 0)
}

function totalCost(): string {
  const val = FEATURES.reduce((sum, f) => sum + parseFloat(f.cost.replace('$', '')), 0)
  return `$${val.toFixed(2)}`
}

function totalTokens(): string {
  const val = FEATURES.reduce((sum, f) => {
    return sum + parseInt(f.tokens.replace(/,/g, ''), 10)
  }, 0)
  return val.toLocaleString()
}

export function StatsStrip(): JSX.Element {
  return (
    <div className={styles.stats}>
      <div className={styles.stat}>
        <div className={styles.k}>Features</div>
        <div className={styles.v}>{FEATURES.length}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Events</div>
        <div className={styles.v}>{totalEvents()}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Invocations</div>
        <div className={styles.v}>{totalInvocations()}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Tokens</div>
        <div className={styles.v}>{totalTokens()}</div>
      </div>
      <div className={styles.stat}>
        <div className={styles.k}>Cost</div>
        <div className={`${styles.v} ${styles.cost}`}>{totalCost()}</div>
      </div>
    </div>
  )
}
