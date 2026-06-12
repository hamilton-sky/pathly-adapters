import { useState } from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { DraftTriageRow } from '../DraftTriageRow/DraftTriageRow'
import styles from './DraftTriageList.module.css'

interface Props {
  hunks: DiffHunk[]
  onToggle: (id: string) => void
  onMarkReviewed: (id: string) => void
  onSetAll: (accept: boolean) => void
}

/**
 * Compact triage list — one row per change with bulk Accept/Reject all.
 * Single-open accordion: opening a row collapses the previously open one,
 * keeping the list short and scannable at high change counts.
 */
export function DraftTriageList({ hunks, onToggle, onMarkReviewed, onSetAll }: Props) {
  const changed = hunks.filter((h) => h.status !== 'unchanged')
  const [openId, setOpenId] = useState<string | null>(changed[0]?.id ?? null)

  function handleOpen(hunk: DiffHunk): void {
    const willOpen = openId !== hunk.id
    setOpenId(willOpen ? hunk.id : null)
    if (willOpen && !hunk.reviewed) onMarkReviewed(hunk.id)
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.title}>CHANGES</span>
        <span className={styles.count}>{changed.length}</span>
        <span className={styles.spacer} />
        <button type="button" className={styles.bulk} onClick={() => onSetAll(true)}>
          Accept all
        </button>
        <button type="button" className={styles.bulk} onClick={() => onSetAll(false)}>
          Reject all
        </button>
      </div>
      <div className={styles.body}>
        {changed.map((hunk) => (
          <DraftTriageRow
            key={hunk.id}
            hunk={hunk}
            open={openId === hunk.id}
            onOpen={() => handleOpen(hunk)}
            onToggle={onToggle}
          />
        ))}
      </div>
    </div>
  )
}
