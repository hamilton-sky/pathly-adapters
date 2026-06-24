import React from 'react'
import { GitCompare } from 'lucide-react'
import type { Comment } from '../../useComments'
import styles from './CommentsPanelRail.module.css'

interface Props {
  comments: Comment[]
  /** A pending comment-revision draft exists — show the diff indicator. */
  hasDraft?: boolean
  onExpand: () => void
}

export function CommentsPanelRail({ comments, hasDraft, onExpand }: Props): JSX.Element {
  const unresolved = comments.filter((c) => !c.resolved)

  return (
    <button
      type="button"
      className={styles.rail}
      onClick={onExpand}
      aria-label={`Open comments — ${unresolved.length} open${hasDraft ? ', revisions ready' : ''}`}
      aria-expanded="false"
    >
      {/* Revisions-ready indicator — opens the panel where the Diff button lives */}
      {hasDraft && <GitCompare className={styles.draftIcon} size={13} aria-hidden="true" />}

      {/* Count badge — always shown, "0" when no open comments */}
      <span className={styles.count} aria-hidden="true">
        {unresolved.length}
      </span>

      {/* One colored dot per unresolved comment (capped at 8) */}
      {unresolved.length > 0 && (
        <div className={styles.dots} aria-hidden="true">
          {unresolved.slice(0, 8).map((c) => (
            <span key={c.id} className={styles.dot} data-color={c.color} />
          ))}
          {unresolved.length > 8 && (
            <span className={styles.dotMore}>+{unresolved.length - 8}</span>
          )}
        </div>
      )}

      {/* Vertical "Comments" label at the bottom */}
      <span className={styles.label} aria-hidden="true">Comments</span>
    </button>
  )
}
