import type { FeatureData } from '../types'
import { StageDots } from '../StageDots'
import { StatePill } from '../StatePill'
import styles from './FeatureStack.module.css'

interface FeatureStackProps {
  features: FeatureData[]
  onRowClick: (feature: FeatureData) => void
}

/** Dense list (☰) view of the feature collection — one row per feature. */
export function FeatureStack({ features, onRowClick }: FeatureStackProps): JSX.Element {
  return (
    <div className={styles.stack}>
      <div className={styles.header}>
        <span className={styles.h}>Feature</span>
        <span className={styles.h}>Pipeline</span>
        <span className={`${styles.h} ${styles.r}`}>Events</span>
        <span className={`${styles.h} ${styles.r}`}>Invocations</span>
        <span className={`${styles.h} ${styles.r}`}>Tokens</span>
        <span className={`${styles.h} ${styles.r}`}>Cost</span>
        <span className={`${styles.h} ${styles.r}`}>State</span>
      </div>
      {features.map((f) => (
        <button key={f.name} type="button" className={styles.row} onClick={() => onRowClick(f)} aria-label={`Open ${f.name}`}>
          <span className={styles.name}>{f.name}</span>
          <span className={styles.dots}><StageDots dots={f.dots} compact /></span>
          <span className={styles.num}>{f.events}</span>
          <span className={styles.num}>{f.inv}</span>
          <span className={styles.num}>{f.tokens}</span>
          <span className={`${styles.num} ${styles.cost}`}>{f.cost}</span>
          <span className={styles.state}><StatePill state={f.state} /></span>
        </button>
      ))}
    </div>
  )
}
