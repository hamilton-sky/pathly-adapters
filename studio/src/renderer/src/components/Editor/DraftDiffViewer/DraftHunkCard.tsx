import { useState } from 'react'
import type { DiffHunk } from './useDraftDiff'
import styles from './DraftHunkCard.module.css'

interface Props {
  hunk: DiffHunk
  onToggle: (id: string) => void
  onMarkReviewed: (id: string) => void
}

const BADGE_LABEL: Record<DiffHunk['status'], string> = {
  added: 'ADDED',
  removed: 'REMOVED',
  changed: 'CHANGED',
  unchanged: '',
}

function firstLine(text: string | null): string {
  if (!text) return ''
  return text.split('\n').map((l) => l.trim()).find(Boolean) ?? ''
}

function toggleLabel(hunk: DiffHunk): string {
  if (hunk.status === 'added') return hunk.accepted ? 'Including' : 'Excluded'
  if (hunk.status === 'removed') return hunk.accepted ? 'Keeping' : 'Discarding'
  return hunk.accepted ? 'Using draft' : 'Using original'
}

export function DraftHunkCard({ hunk, onToggle, onMarkReviewed }: Props) {
  const [expanded, setExpanded] = useState(false)

  function handleExpand(): void {
    if (!expanded && !hunk.reviewed) onMarkReviewed(hunk.id)
    setExpanded((v) => !v)
  }

  const heading = hunk.heading === '__preamble__' ? 'Preamble' : hunk.heading
  const preview = firstLine(hunk.draftContent ?? hunk.originalContent)

  return (
    <div className={`${styles.card} ${styles[hunk.status]}`}>
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
        {!expanded && preview && <div className={styles.preview}>{preview}</div>}
      </button>

      {expanded && (
        <div className={styles.expanded}>
          {hunk.status !== 'added' && (
            <div className={styles.block}>
              <div className={styles.blockLabel}>ORIGINAL</div>
              <pre className={styles.blockText}>{hunk.originalContent ?? ''}</pre>
            </div>
          )}
          {hunk.status !== 'removed' && (
            <div className={styles.block}>
              <div className={styles.blockLabel}>DRAFT</div>
              <pre className={styles.blockText}>{hunk.draftContent ?? ''}</pre>
            </div>
          )}
        </div>
      )}

      <div className={styles.cardFooter}>
        <button type="button" className={styles.toggleChip} onClick={() => onToggle(hunk.id)}>
          {toggleLabel(hunk)}
        </button>
      </div>
    </div>
  )
}
