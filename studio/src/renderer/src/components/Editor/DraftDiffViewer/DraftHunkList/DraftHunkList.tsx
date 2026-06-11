import type { DiffHunk } from '../useDraftDiff'
import { DraftHunkCard } from '../DraftHunkCard/DraftHunkCard'
import styles from './DraftHunkList.module.css'

interface Props {
  hunks: DiffHunk[]
  onToggle: (id: string) => void
  onMarkReviewed: (id: string) => void
}

export function DraftHunkList({ hunks, onToggle, onMarkReviewed }: Props) {
  const changed = hunks.filter((h) => h.status !== 'unchanged')

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>CHANGES</span>
        <span className={styles.countBadge}>{changed.length}</span>
      </div>
      <div className={styles.list}>
        {changed.map((hunk) => (
          <DraftHunkCard key={hunk.id} hunk={hunk} onToggle={onToggle} onMarkReviewed={onMarkReviewed} />
        ))}
      </div>
    </div>
  )
}
