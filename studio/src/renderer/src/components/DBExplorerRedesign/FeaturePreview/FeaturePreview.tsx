import type { FeatureData } from '../types'
import { StageDots } from '../StageDots'
import { StatePill } from '../StatePill'
import styles from './FeaturePreview.module.css'

interface FeaturePreviewProps {
  feature: FeatureData | null
  onClose: () => void
  /** "Open full page →" — hand off to the detail route. */
  onOpenDetail: (feature: FeatureData) => void
}

/**
 * Lightweight preview popover shown when a card is clicked. Enough to decide
 * whether to drill in — key stats + stage strip — with a button to the full page.
 */
export function FeaturePreview({ feature, onClose, onOpenDetail }: FeaturePreviewProps): JSX.Element {
  return (
    <div
      className={styles.overlay}
      {...(feature ? { 'data-open': '' } : {})}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label={feature ? `Preview: ${feature.name}` : 'Feature preview'}
    >
      {feature && (
        <div className={styles.card}>
          <div className={styles.head}>
            <span className={styles.name}>{feature.name}</span>
            <StatePill state={feature.state} />
            <button type="button" className={styles.close} onClick={onClose} aria-label="Close preview">✕</button>
          </div>
          <span className={styles.sub}>Quick preview · last activity {feature.ts}</span>
          <StageDots dots={feature.dots} compact />
          <div className={styles.stats}>
            <Stat k="Events" v={feature.events} />
            <Stat k="Invocations" v={feature.inv} />
            <Stat k="Tokens" v={feature.tokens} />
            <Stat k="Cost" v={feature.cost} cost />
          </div>
          <div className={styles.actions}>
            <button type="button" className={styles.primary} onClick={() => onOpenDetail(feature)}>
              Open full page →
            </button>
            <button type="button" className={styles.secondary} onClick={onClose}>Close</button>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ k, v, cost = false }: { k: string; v: string | number; cost?: boolean }): JSX.Element {
  return (
    <div>
      <div className={styles.sk}>{k}</div>
      <div className={`${styles.sv} ${cost ? styles.cost : ''}`}>{v}</div>
    </div>
  )
}
