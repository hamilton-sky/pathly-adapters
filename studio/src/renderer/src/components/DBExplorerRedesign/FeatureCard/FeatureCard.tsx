import type { FeatureData } from '../types'
import { StageDots } from '../StageDots'
import { StatePill } from '../StatePill'
import styles from './FeatureCard.module.css'

interface FeatureCardProps {
  feature: FeatureData
  /** Card body click → open the lightweight preview popover. */
  onPreview: (feature: FeatureData) => void
  /** ↗ button → jump straight to the full detail page. */
  onOpenDetail: (feature: FeatureData) => void
}

/**
 * A single feature record in the grid. Clicking the body opens a preview;
 * the ↗ corner button skips the preview and opens the full page.
 */
export function FeatureCard({ feature, onPreview, onOpenDetail }: FeatureCardProps): JSX.Element {
  return (
    <div
      className={styles.feat}
      role="button"
      tabIndex={0}
      aria-label={`Preview ${feature.name}`}
      onClick={() => onPreview(feature)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPreview(feature) }
      }}
    >
      <div className={styles.top}>
        <span className={styles.fname}>{feature.name}</span>
        <button
          type="button"
          className={styles.openBtn}
          aria-label={`Open ${feature.name} full page`}
          title="Open full page"
          onClick={(e) => { e.stopPropagation(); onOpenDetail(feature) }}
        >
          ↗
        </button>
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
    </div>
  )
}
