import React, { useState, useRef, useEffect } from 'react'
import { Check, X, Pencil, RotateCcw, Crosshair } from 'lucide-react'
import { Tooltip } from '../../../ui'
import type { Comment, CommentColor } from '../../useComments'
import styles from './CommentItem.module.css'


interface Props {
  comment: Comment
  index: number
  isOrphaned: boolean
  onResolve: (id: string) => void
  onReopen: (id: string) => void
  onRemove: (id: string) => void
  onEdit: (id: string, body: string) => void
  onScrollTo: (id: string) => void
}

export function CommentItem({
  comment, index, isOrphaned, onResolve, onReopen, onRemove, onEdit, onScrollTo,
}: Props): JSX.Element {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)
  const itemRef = useRef<HTMLDivElement>(null)

  // Set color + glow CSS variables imperatively (allowed exception for dynamic values)
  useEffect(() => {
    const el = itemRef.current
    if (!el) return
    if (comment.resolved) {
      el.style.setProperty('--comment-item-color', 'var(--border-color)')
    } else {
      el.style.setProperty('--comment-item-color', `var(--comment-${comment.color}-border)`)
    }
  }, [comment.color, comment.resolved])

  function handleSave(): void {
    const trimmed = draft.trim()
    if (trimmed) { onEdit(comment.id, trimmed); setEditing(false) }
  }

  function handleCancel(): void { setDraft(comment.body); setEditing(false) }

  const canLocate = !comment.resolved && !isOrphaned
  const anchorFull = comment.lineText
  const anchorShort = anchorFull.length > 55 ? `${anchorFull.slice(0, 55).trimEnd()}…` : anchorFull

  return (
    <div
      ref={itemRef}
      className={[
        styles.item,
        comment.resolved ? styles.resolved : '',
        isOrphaned ? styles.orphaned : '',
      ].filter(Boolean).join(' ')}
      onClick={canLocate && !editing ? () => onScrollTo(comment.id) : undefined}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && canLocate && !editing) onScrollTo(comment.id) }}
      aria-label={`Comment ${index}: ${isOrphaned ? 'anchor lost' : anchorShort}`}
    >
      {/* â”€â”€ Top row: badge â€¢ anchor quote â€¢ action icons â”€â”€ */}
      <div className={styles.topRow}>
        <span className={`${styles.badge} ${comment.resolved ? styles.resolvedBadge : ''}`}>
          {index}
        </span>

        <span
          className={`${styles.anchorQuote} ${isOrphaned ? styles.anchorLost : ''}`}
          title={isOrphaned ? 'Original anchor text not found in document' : anchorFull}
        >
          {isOrphaned ? 'âš  anchor lost' : `"${anchorShort}"`}
        </span>

        <div className={styles.iconRow} onClick={(e) => e.stopPropagation()}>
          {canLocate && !editing && (
            <Tooltip label="Jump to anchor" placement="top">
              <button type="button" className={styles.iconBtn} aria-label="Jump to anchor" onClick={() => onScrollTo(comment.id)}>
                <Crosshair size={15} />
              </button>
            </Tooltip>
          )}
          {!comment.resolved && !editing && (
            <Tooltip label="Resolve" placement="top">
              <button type="button" className={`${styles.iconBtn} ${styles.resolveBtn}`} aria-label="Resolve" onClick={() => onResolve(comment.id)}>
                <Check size={15} />
              </button>
            </Tooltip>
          )}
          {comment.resolved && !editing && (
            <Tooltip label="Reopen" placement="top">
              <button type="button" className={styles.iconBtn} aria-label="Reopen" onClick={() => onReopen(comment.id)}>
                <RotateCcw size={15} />
              </button>
            </Tooltip>
          )}
          {!editing && (
            <Tooltip label="Edit" placement="top">
              <button type="button" className={styles.iconBtn} aria-label="Edit" onClick={() => { setDraft(comment.body); setEditing(true) }}>
                <Pencil size={15} />
              </button>
            </Tooltip>
          )}
          <Tooltip label="Delete" placement="top">
            <button type="button" className={`${styles.iconBtn} ${styles.deleteBtn}`} aria-label="Delete" onClick={() => onRemove(comment.id)}>
              <X size={15} />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* â”€â”€ Comment body / edit area â”€â”€ */}
      {editing ? (
        <>
          <textarea
            className={styles.editArea}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            rows={3}
            autoFocus
          />
          <div className={styles.editActions} onClick={(e) => e.stopPropagation()}>
            <button type="button" className={styles.saveBtn} disabled={!draft.trim()} onClick={handleSave}>
              <Check size={14} /> Save
            </button>
            <button type="button" className={styles.cancelBtn} onClick={handleCancel}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <p className={styles.body}>{comment.body}</p>
      )}
    </div>
  )
}
