import { useState } from 'react'
import styles from './DraftDiffFooter.module.css'

interface Props {
  unreviewedCount: number
  acceptedCount: number
  totalChanged: number
  onDiscard: () => void
  onClose: () => void
  onApply: () => void
}

export function DraftDiffFooter({
  unreviewedCount,
  acceptedCount,
  totalChanged,
  onDiscard,
  onClose,
  onApply,
}: Props) {
  const [showConfirm, setShowConfirm] = useState(false)

  if (showConfirm) {
    return (
      <div className={styles.footer}>
        <span className={styles.confirmText}>Permanently delete draft?</span>
        <div className={styles.confirmActions}>
          <button type="button" className={styles.btnDanger} onClick={onDiscard}>
            Yes, discard
          </button>
          <button type="button" className={styles.btnCancel} onClick={() => setShowConfirm(false)}>
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.footerWrap}>
      {unreviewedCount > 0 && (
        <div className={styles.warning}>You have {unreviewedCount} unreviewed sections</div>
      )}
      <div className={styles.footer}>
        <button type="button" className={styles.btnDiscard} onClick={() => setShowConfirm(true)}>
          Discard agent changes
        </button>
        <div className={styles.footerRight}>
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            disabled={acceptedCount === 0}
            onClick={onApply}
          >
            Apply {acceptedCount} of {totalChanged} changes
          </button>
        </div>
      </div>
    </div>
  )
}
