import { useState } from 'react'
import type { DiffHunk } from './useDraftDiff'
import { DiffCodeBlock } from './DiffCodeBlock'
import styles from './DraftHunkCard.module.css'

interface Props {
  hunk: DiffHunk
  onToggle: (id: string) => void
  onMarkReviewed: (id: string) => void
}

const BADGE_LABEL: Record<DiffHunk['status'], string> = {
  added:     'ADDED',
  removed:   'REMOVED',
  changed:   'CHANGED',
  unchanged: '',
}

function toggleLabel(hunk: DiffHunk): string {
  if (hunk.status === 'added')   return hunk.accepted ? 'Including'    : 'Excluded'
  if (hunk.status === 'removed') return hunk.accepted ? 'Keeping'      : 'Discarding'
  return hunk.accepted ? 'Using draft' : 'Using original'
}

export function DraftHunkCard({ hunk, onToggle, onMarkReviewed }: Props) {
  const [expanded, setExpanded] = useState(false)

  function handleExpand(): void {
    if (!expanded && !hunk.reviewed) onMarkReviewed(hunk.id)
    setExpanded((v) => !v)
  }

  const paraMatch = hunk.heading.match(/^__para_(\d+)__$/)
  const heading = hunk.heading === '__preamble__'
    ? 'Preamble'
    : paraMatch
      ? `Paragraph ${Number(paraMatch[1]) + 1}`
      : hunk.heading
  const origContent = hunk.status !== 'added'   ? (hunk.originalContent ?? '') : null
  const draftContent = hunk.status !== 'removed' ? (hunk.draftContent ?? '')   : null

  return (
    <div className={styles.card} data-status={hunk.status}>

      <button
        type="button"
        className={styles.cardBody}
        onClick={handleExpand}
        {...(expanded ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <div className={styles.cardTop}>
          <span className={styles.heading}>{heading}</span>
          <span className={styles.typeBadge}>{BADGE_LABEL[hunk.status]}</span>
        </div>
        <div className={styles.cardMeta}>
          <span className={styles.expandHint}>{expanded ? '▾ collapse' : '▸ show diff'}</span>
          {!hunk.reviewed && <span className={styles.unreviewed}>unreviewed</span>}
        </div>
      </button>

      {expanded && (
        <div className={styles.diffWrap}>
          <DiffCodeBlock original={origContent} draft={draftContent} />
        </div>
      )}

      <div className={styles.cardFooter}>
        <button
          type="button"
          className={`${styles.toggleChip} ${hunk.accepted ? styles.toggleChipAccepted : ''}`}
          onClick={() => onToggle(hunk.id)}
        >
          {toggleLabel(hunk)}
        </button>
      </div>
    </div>
  )
}
