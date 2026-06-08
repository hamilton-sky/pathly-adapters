import React, { useState } from 'react'
import { Check, X, Pencil } from 'lucide-react'
import type { Comment } from '../../useComments'
import styles from './CommentItem.module.css'

interface Props {
  comment: Comment
  onResolve: (id: string) => void
  onRemove: (id: string) => void
  onEdit: (id: string, body: string) => void
}

export function CommentItem({ comment, onResolve, onRemove, onEdit }: Props): JSX.Element {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(comment.body)

  function handleSave(): void {
    const trimmed = draft.trim()
    if (trimmed) { onEdit(comment.id, trimmed); setEditing(false) }
  }

  function handleCancel(): void {
    setDraft(comment.body)
    setEditing(false)
  }

  return (
    <div className={`${styles.item} ${comment.resolved ? styles.resolved : ''}`}>
      <div className={styles.anchor}>
        <span className={styles.lineNum}>L{comment.lineNumber}</span>
        {comment.lineText && (
          <span className={styles.lineText} title={comment.lineText}>
            {comment.lineText.slice(0, 50).trim()}
          </span>
        )}
      </div>

      {editing ? (
        <>
          <textarea
            className={styles.editArea}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            autoFocus
          />
          <div className={styles.editActions}>
            <button
              type="button"
              className={styles.saveBtn}
              onClick={handleSave}
              disabled={!draft.trim()}
            >
              <Check size={11} /> Save
            </button>
            <button type="button" className={styles.cancelEditBtn} onClick={handleCancel}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <p className={styles.body}>{comment.body}</p>
      )}

      {!comment.resolved && !editing && (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.resolveBtn}
            onClick={() => onResolve(comment.id)}
            aria-label="Resolve comment"
          >
            <Check size={11} /> Resolve
          </button>
          <button
            type="button"
            className={styles.editBtn}
            onClick={() => { setDraft(comment.body); setEditing(true) }}
            aria-label="Edit comment"
          >
            <Pencil size={11} />
          </button>
          <button
            type="button"
            className={styles.removeBtn}
            onClick={() => onRemove(comment.id)}
            aria-label="Delete comment"
          >
            <X size={11} />
          </button>
        </div>
      )}
    </div>
  )
}
