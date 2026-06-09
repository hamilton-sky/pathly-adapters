import type { StageLogEntry } from '../../../store/runnerStore'
import styles from './StageCard.module.css'

interface Props {
  entry: StageLogEntry
  viewMode: 'grid' | 'list'
  onClick: () => void
}

export function StageCard({ entry, viewMode, onClick }: Props): JSX.Element {
  const durationSec = entry.durationMs != null ? (entry.durationMs / 1000).toFixed(1) + 's' : '—'
  const costStr = entry.costUsd != null ? '$' + entry.costUsd.toFixed(3) : '—'
  const exitOk = entry.exitCode === 0
  const pending = entry.exitCode === null
  const adapterClass = entry.adapter === 'claude' ? styles.adapterClaude : entry.adapter === 'codex' ? styles.adapterCodex : entry.adapter === 'agy' ? styles.adapterAgy : ''
  const dotClass = pending ? styles.dotPending : exitOk ? styles.dotOk : styles.dotFail
  const snippet = entry.result ? entry.result.split('\n')[0] : null

  if (viewMode === 'grid') {
    return (
      <button type="button" className={`${styles.card} ${styles.cardGrid}`} onClick={onClick}>
        <div className={styles.gridTop}>
          <span className={styles.stageName}>{entry.stage}</span>
          <span className={dotClass} />
        </div>
        {snippet && <p className={styles.snippet}>{snippet}</p>}
        <div className={styles.gridMeta}>
          {entry.adapter && <span className={`${styles.adapterPill} ${adapterClass}`}>{entry.adapter}</span>}
          <span className={styles.metaItem}>{durationSec}</span>
          <span className={styles.metaItem}>{costStr}</span>
        </div>
      </button>
    )
  }

  return (
    <button type="button" className={`${styles.card} ${styles.cardList}`} onClick={onClick}>
      <span className={styles.stageName}>{entry.stage}</span>
      {entry.adapter && <span className={`${styles.adapterPill} ${adapterClass}`}>{entry.adapter}</span>}
      {snippet && <span className={styles.snippetList}>{snippet}</span>}
      <span className={styles.metaItem}>{durationSec}</span>
      <span className={styles.metaItem}>{costStr}</span>
      <span className={dotClass} />
    </button>
  )
}
