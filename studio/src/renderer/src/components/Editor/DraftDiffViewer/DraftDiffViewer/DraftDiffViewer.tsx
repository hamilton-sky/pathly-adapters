import { useState } from 'react'
import { useDraftDiff } from '../useDraftDiff'
import type { DiffComment } from '../useDraftDiff'
import { useViewMode } from '../useViewMode'
import { ViewToggle } from '../ViewToggle/ViewToggle'
import { DraftHunkList } from '../DraftHunkList/DraftHunkList'
import { DraftTriageList } from '../DraftTriageList/DraftTriageList'
import { CodeDiffView } from '../CodeDiffView/CodeDiffView'
import { DraftEditView } from '../DraftEditView/DraftEditView'
import { DraftPreviewPanel } from '../DraftPreviewPanel/DraftPreviewPanel'
import { DraftDiffFooter } from '../DraftDiffFooter/DraftDiffFooter'
import type { ViewMode } from '../useViewMode'
import styles from './DraftDiffViewer.module.css'

export interface DraftDiffViewerProps {
  originalPath: string
  draftPath: string
  /** Provenance of the draft — drives the title and whether comment refs are shown. */
  source?: 'split' | 'comments'
  /** Unresolved comments to map onto hunks (comment-revision diffs only). */
  comments?: DiffComment[]
  onApply: (newContent: string) => void
  onClose: () => void
  onDiscard: () => void
}

function diffTitle(source?: 'split' | 'comments'): string {
  if (source === 'split') return 'Reviewing AI Split'
  if (source === 'comments') return 'Reviewing comment revisions'
  return 'Reviewing draft'
}

function filename(path: string): string {
  return path.split(/[\\/]/).pop() ?? path
}

type ContentProps = DraftDiffViewerProps & { view: ViewMode; onRetry: () => void }

function DiffContent({ originalPath, draftPath, comments, onApply, onClose, onDiscard, view, onRetry }: ContentProps) {
  const diff = useDraftDiff(originalPath, draftPath, comments)
  // null = follow the per-section accept/reject choices; a string = the user's
  // manual edit of the result, which then wins on Apply.
  const [edited, setEdited] = useState<string | null>(null)

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

  // No changed sections — the draft is identical to the original (a common no-op AI Split).
  // Show it plainly instead of silently closing (which read as a flicker-and-vanish), and offer
  // to discard the useless draft so the Diff pill stops mis-lighting on every open.
  if (diff.totalChanged === 0) {
    return (
      <div className={styles.state}>
        <div className={styles.stateText}>
          No changes to review — this draft is identical to the original.
        </div>
        <div className={styles.stateActions}>
          <button type="button" className={styles.btnPrimary} onClick={onDiscard}>
            Discard draft
          </button>
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    )
  }

  const result = diff.reconstruct()

  return (
    <>
      {view === 'cards' ? (
        <div className={styles.body}>
          <DraftHunkList hunks={diff.hunks} onToggle={diff.toggle} onMarkReviewed={diff.markReviewed} />
          <DraftPreviewPanel content={result} changedHunks={diff.hunks} />
        </div>
      ) : view === 'list' ? (
        <DraftTriageList
          hunks={diff.hunks}
          onToggle={diff.toggle}
          onMarkReviewed={diff.markReviewed}
          onSetAll={diff.setAll}
        />
      ) : view === 'code' ? (
        <CodeDiffView hunks={diff.hunks} fileName={filename(originalPath)} />
      ) : (
        <DraftEditView
          value={edited ?? result}
          onChange={setEdited}
          edited={edited !== null}
          onReset={() => setEdited(null)}
        />
      )}
      <DraftDiffFooter
        unreviewedCount={diff.unreviewedCount}
        acceptedCount={diff.acceptedCount}
        totalChanged={diff.totalChanged}
        editedManually={edited !== null}
        onDiscard={onDiscard}
        onClose={onClose}
        onApply={() => onApply(edited ?? result)}
      />
    </>
  )
}

export function DraftDiffViewer(props: DraftDiffViewerProps) {
  const [retryKey, setRetryKey] = useState(0)
  const [view, setView] = useViewMode('cards')

  return (
    <div className={styles.backdrop} onClick={props.onClose}>
      <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="draft-diff-title" onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div id="draft-diff-title" className={styles.title}>
            {diffTitle(props.source)} — <span className={styles.file}>{filename(props.draftPath)}</span>
          </div>
          <span className={styles.spacer} />
          <ViewToggle value={view} onChange={setView} />
        </div>
        <DiffContent key={retryKey} {...props} view={view} onRetry={() => setRetryKey((k) => k + 1)} />
      </div>
    </div>
  )
}
