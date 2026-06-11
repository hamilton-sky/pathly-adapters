import { useState } from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { DiffCodeBlock } from '../DiffCodeBlock/DiffCodeBlock'
import { StatusBadge } from '../StatusBadge/StatusBadge'
import { AcceptToggleChip } from '../AcceptToggleChip/AcceptToggleChip'
import { Chevron } from '../icons/Icons'
import { displayHeading, previewText } from '../hunkLabels'
import styles from './DraftHunkCard.module.css'

interface Props {
  hunk: DiffHunk
  onToggle: (id: string) => void
  onMarkReviewed: (id: string) => void
}

/** One section hunk as a notebook-style cell. Click to expand its word diff. */
export function DraftHunkCard({ hunk, onToggle, onMarkReviewed }: Props) {
  const [expanded, setExpanded] = useState(false)

  function handleExpand(): void {
    if (!expanded && !hunk.reviewed) onMarkReviewed(hunk.id)
    setExpanded((v) => !v)
  }

  function handleKeyDown(e: React.KeyboardEvent): void {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleExpand()
    }
  }

  const origContent = hunk.status !== 'added' ? hunk.originalContent ?? '' : null
  const draftContent = hunk.status !== 'removed' ? hunk.draftContent ?? '' : null

  return (
    <div
      className={styles.card}
      data-status={hunk.status}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onClick={handleExpand}
      onKeyDown={handleKeyDown}
    >
      <div className={styles.strip}>
        <StatusBadge status={hunk.status} />
        <span className={styles.stripDiv} />
        <span className={styles.chevron}>
          <Chevron open={expanded} />
        </span>
      </div>

      <div className={styles.title}>{displayHeading(hunk.heading)}</div>

      {!expanded && <div className={styles.preview}>{previewText(hunk).slice(0, 46)}…</div>}

      {expanded && (
        <div className={styles.diffWrap} onClick={(e) => e.stopPropagation()}>
          <DiffCodeBlock original={origContent} draft={draftContent} />
        </div>
      )}

      <div className={styles.foot}>
        {!hunk.reviewed && <span className={styles.unreviewed}>unreviewed</span>}
        <span className={styles.spacer} />
        <AcceptToggleChip hunk={hunk} onToggle={onToggle} />
      </div>
    </div>
  )
}
