import type { FeatureData } from '../dbExplorerData'
import { StageDots } from '../StageDots'
import { StatePill } from '../StatePill'
import styles from './FeatureCard.module.css'

interface FeatureCardProps {
  feature: FeatureData
  onClick: () => void
}

export function FeatureCard({ feature, onClick }: FeatureCardProps): JSX.Element {
  return (
    <button type="button" className={styles.feat} onClick={onClick} aria-label={`Open ${feature.name}`}>
      <div className={styles.top}>
        <span className={styles.fname}>{feature.name}</span>
      </div>

      <StageDots dots={feature.dots} />

      <div className={styles.metrics}>
        <div>
          <div className={styles.mk}>Events</div>
          <div className={styles.mv}>{feature.events}</div>
        </div>
        <div>
          <div className={styles.mk}>Invocations</div>
          <div className={styles.mv}>{feature.inv}</div>
        </div>
        <div>
          <div className={styles.mk}>Tokens</div>
          <div className={styles.mv}>{feature.tokens}</div>
        </div>
        <div>
          <div className={styles.mk}>Cost</div>
          <div className={`${styles.mv} ${styles.cost}`}>{feature.cost}</div>
        </div>
      </div>

      <div className={styles.foot}>
        <span className={styles.ts}>{feature.ts}</span>
        <StatePill state={feature.state} />
      </div>
    </button>
  )
}
