import { useState } from 'react'
import type { FeatureData } from './dbExplorerData'
import { FEATURES } from './dbExplorerData'
import { StatsStrip } from './StatsStrip'
import { FeatureGrid } from './FeatureGrid'
import { FeatureModal } from './FeatureModal'
import styles from './DBExplorer.module.css'

export function DBExplorer(): JSX.Element {
  const [modalFeature, setModalFeature] = useState<FeatureData | null>(null)

  return (
    <div className={styles.panel}>
      <DBExplorerHeader />
      <StatsStrip />
      <FeatureGrid features={FEATURES} onCardClick={setModalFeature} />
      <FeatureModal feature={modalFeature} onClose={() => setModalFeature(null)} />
    </div>
  )
}

function DBExplorerHeader(): JSX.Element {
  return (
    <div className={styles.header}>
      <div className={styles.titleGroup}>
        <h2 className={styles.title}>DB Explorer</h2>
        <span className={styles.subtitle}>Pipeline database — features, events, agent invocations</span>
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.btnB}>
          <span>↻</span> Refresh
        </button>
        <button type="button" className={styles.btnB}>
          <span>⊞</span> Run Migration
        </button>
        <button type="button" className={styles.btnB}>
          <span>↓</span> Export JSON
        </button>
      </div>
    </div>
  )
}
