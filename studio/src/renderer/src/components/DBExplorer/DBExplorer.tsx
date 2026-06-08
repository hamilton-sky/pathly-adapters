import { useState } from 'react'
import type { FeatureData } from './dbExplorerData'
import { FEATURES } from './dbExplorerData'
import { StatsStrip } from './StatsStrip'
import { FeatureGrid } from './FeatureGrid'
import { FeatureStack } from './FeatureStack'
import { FeatureModal } from './FeatureModal'
import styles from './DBExplorer.module.css'

type ViewMode = 'grid' | 'stack'

export function DBExplorer(): JSX.Element {
  const [modalFeature, setModalFeature] = useState<FeatureData | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')

  return (
    <div className={styles.panel}>
      <DBExplorerHeader viewMode={viewMode} onViewMode={setViewMode} />
      <StatsStrip />
      {viewMode === 'grid'
        ? <FeatureGrid features={FEATURES} onCardClick={setModalFeature} />
        : <FeatureStack features={FEATURES} onRowClick={setModalFeature} />
      }
      <FeatureModal feature={modalFeature} onClose={() => setModalFeature(null)} />
    </div>
  )
}

interface HeaderProps {
  viewMode: ViewMode
  onViewMode: (m: ViewMode) => void
}

function DBExplorerHeader({ viewMode, onViewMode }: HeaderProps): JSX.Element {
  return (
    <div className={styles.header}>
      <div className={styles.titleGroup}>
        <h2 className={styles.title}>DB Explorer</h2>
        <span className={styles.subtitle}>Pipeline database — features, events, agent invocations</span>
      </div>
      <div className={styles.actions}>
        <div className={styles.viewToggle}>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === 'grid' ? styles.toggleBtnActive : ''}`}
            onClick={() => onViewMode('grid')}
            aria-label="Grid view"
            aria-pressed={viewMode === 'grid'}
          >
            ⊞
          </button>
          <button
            type="button"
            className={`${styles.toggleBtn} ${viewMode === 'stack' ? styles.toggleBtnActive : ''}`}
            onClick={() => onViewMode('stack')}
            aria-label="Stack view"
            aria-pressed={viewMode === 'stack'}
          >
            ☰
          </button>
        </div>
        <button type="button" className={styles.btnB}>↻ Refresh</button>
        <button type="button" className={styles.btnB}>⊞ Run Migration</button>
        <button type="button" className={styles.btnB}>↓ Export JSON</button>
      </div>
    </div>
  )
}
