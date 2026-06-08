import React from 'react'
import { Check, X } from 'lucide-react'
import type { Comment } from '../../useComments'
import styles from './CommentItem.module.css'

interface Props {
  comment: Comment
  onResolve: (id: string) => void
  onRemove: (id: string) => void
}

export function CommentItem({ comment, onResolve, onRemove }: Props): JSX.Element {
  return (
    <div className={`${styles.item} ${comment.resolved ? styles.resolved : ''}`}>
      <div className={styles.anchor}>
        <span className={styles.lineNum}>L{comment.lineNumber}</span>
        {comment.lineText && (
          <span className={styles.lineText}>{comment.lineText.slice(0, 50).trim()}</span>
        )}
      </div>
      <p className={styles.body}>{comment.body}</p>
      {!comment.resolved && (
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
