import type { FeatureData } from '../dbExplorerData'
import { StageDots } from '../StageDots'
import { StatePill } from '../StatePill'
import styles from './FeatureStack.module.css'

interface FeatureStackProps {
  features: FeatureData[]
  onRowClick: (feature: FeatureData) => void
}

export function FeatureStack({ features, onRowClick }: FeatureStackProps): JSX.Element {
  return (
    <div className={styles.stack}>
      <div className={styles.header}>
        <span className={styles.hName}>Feature</span>
        <span className={styles.hDots}>Pipeline</span>
        <span className={styles.hNum}>Events</span>
        <span className={styles.hNum}>Invocations</span>
        <span className={styles.hNum}>Tokens</span>
        <span className={styles.hNum}>Cost</span>
        <span className={styles.hProgress}>Progress</span>
        <span className={styles.hState}>State</span>
      </div>
      {features.map((f) => (
        <button
          key={f.name}
          type="button"
          className={styles.row}
          onClick={() => onRowClick(f)}
          aria-label={`Open ${f.name}`}
        >
          <span className={styles.name}>{f.name}</span>
          <span className={styles.dots}><StageDots dots={f.dots} compact /></span>
          <span className={styles.num}>{f.events}</span>
          <span className={styles.num}>{f.inv}</span>
          <span className={styles.num}>{f.tokens}</span>
          <span className={`${styles.num} ${styles.cost}`}>{f.cost}</span>
          <span className={styles.progress}>
            <progress className={styles.progressEl} value={f.done} max={f.total} />
            <span className={styles.frac}>{f.done}/{f.total}</span>
          </span>
          <span className={styles.state}><StatePill state={f.state} /></span>
        </button>
      ))}
    </div>
  )
}
