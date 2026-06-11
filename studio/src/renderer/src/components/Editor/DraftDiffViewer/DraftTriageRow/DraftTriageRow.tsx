import React from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { DiffCodeBlock } from '../DiffCodeBlock/DiffCodeBlock'
import { StatusBadge } from '../StatusBadge/StatusBadge'
import { AcceptToggleChip } from '../AcceptToggleChip/AcceptToggleChip'
import { Chevron } from '../icons/Icons'
import { displayHeading, previewText } from '../hunkLabels'
import { countWordChanges } from '../diffUtils'
import styles from './DraftTriageRow.module.css'

interface Props {
  hunk: DiffHunk
  open: boolean
  onOpen: () => void
  onToggle: (id: string) => void
}

const STATUS_DOT: Record<string, string> = {
  added: styles.dotAdded,
  removed: styles.dotRemoved,
  changed: styles.dotChanged,
}

/** Dense single-line change row; clicking it opens the word diff inline. */
export function DraftTriageRow({ hunk, open, onOpen, onToggle }: Props) {
  const { added, removed } = countWordChanges(hunk.originalContent, hunk.draftContent)
  const origContent = hunk.status !== 'added' ? hunk.originalContent ?? '' : null
  const draftContent = hunk.status !== 'removed' ? hunk.draftContent ?? '' : null

  return (
    <div className={`${styles.row} ${open ? styles.open : ''}`}>
      <div
        className={styles.main}
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={onOpen}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen()
          }
        }}
      >
        <span className={`${styles.dot} ${STATUS_DOT[hunk.status] ?? ''}`} />
        <span className={styles.name}>{displayHeading(hunk.heading)}</span>
        <span className={styles.preview}>{previewText(hunk).slice(0, 52)}…</span>
        <span className={styles.stat}>
          <span className={styles.add}>+{added}</span>
          <span className={styles.rem}>−{removed}</span>
        </span>
        <StatusBadge status={hunk.status} />
        <span className={styles.chevron}>
          <Chevron open={open} />
        </span>
      </div>

      {open && (
        <div className={styles.detail}>
          <DiffCodeBlock original={origContent} draft={draftContent} />
          <div className={styles.detailRow}>
            {!hunk.reviewed && <span className={styles.unreviewed}>unreviewed</span>}
            <span className={styles.spacer} />
            <AcceptToggleChip hunk={hunk} onToggle={onToggle} />
          </div>
        </div>
      )}
    </div>
  )
}
