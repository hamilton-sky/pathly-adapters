import { useState, useEffect } from 'react'
import { useDraftDiff } from './useDraftDiff'
import { DraftHunkList } from './DraftHunkList'
import { DraftPreviewPanel } from './DraftPreviewPanel'
import { DraftDiffFooter } from './DraftDiffFooter'
import { useToastStore } from '../../../store/toastStore'
import styles from './DraftDiffViewer.module.css'

interface Props {
  originalPath: string
  draftPath: string
  onApply: (newContent: string) => void
  onClose: () => void
  onDiscard: () => void
}

function filename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}

interface ContentProps extends Props {
  onRetry: () => void
}

function DiffContent({ originalPath, draftPath, onApply, onClose, onDiscard, onRetry }: ContentProps) {
  const diff = useDraftDiff(originalPath, draftPath)
  const pushToast = useToastStore((s) => s.push)

  useEffect(() => {
    if (!diff.loading && !diff.error && diff.totalChanged === 0) {
      pushToast('No changes detected — draft is identical to the original', 'info')
      onClose()
    }
  }, [diff.loading, diff.error, diff.totalChanged, onClose, pushToast])

  if (diff.loading) {
    return <div className={styles.state}>Loading diff…</div>
  }

  if (diff.error) {
    return (
      <div className={styles.state}>
        <div className={styles.stateText}>Could not load draft</div>
        <div className={styles.stateActions}>
          <button type="button" className={styles.btnPrimary} onClick={onRetry}>
            Retry
          </button>
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Dismiss
          </button>
        </div>
      </div>
    )
  }

  if (diff.totalChanged === 0) {
    return null
  }

  return (
    <>
      <div className={styles.body}>
        <DraftHunkList hunks={diff.hunks} onToggle={diff.toggle} onMarkReviewed={diff.markReviewed} />
        <DraftPreviewPanel content={diff.reconstruct()} changedHunks={diff.hunks} />
      </div>
      <DraftDiffFooter
        unreviewedCount={diff.unreviewedCount}
        acceptedCount={diff.acceptedCount}
        totalChanged={diff.totalChanged}
        onDiscard={onDiscard}
        onClose={onClose}
        onApply={() => onApply(diff.reconstruct())}
      />
    </>
  )
}

export function DraftDiffViewer(props: Props) {
  const [retryKey, setRetryKey] = useState(0)

  return (
    <div className={styles.backdrop} onClick={props.onClose}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="draft-diff-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div id="draft-diff-title" className={styles.title}>Reviewing draft — {filename(props.draftPath)}</div>
        </div>
        <DiffContent key={retryKey} {...props} onRetry={() => setRetryKey((k) => k + 1)} />
      </div>
    </div>
  )
}
