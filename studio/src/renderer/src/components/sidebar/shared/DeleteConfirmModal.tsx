import { useEffect, useRef } from 'react'
import type { PathlyItem } from '../../../types'
import { useFocusTrap } from '../../../hooks/useFocusTrap'
import styles from '../Sidebar.module.css'

interface Props {
  item: PathlyItem
  onCancel: () => void
  onConfirm: () => void
}

export function DeleteConfirmModal({ item, onCancel, onConfirm }: Props): JSX.Element {
  const boxRef = useRef<HTMLDivElement>(null)
  useFocusTrap(boxRef)

  useEffect(() => {
    function onKey(e: KeyboardEvent): void { if (e.key === 'Escape') onCancel() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div className={styles.modalOverlay}>
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-modal-title"
        className={styles.modalBox}
      >
        <p id="delete-modal-title" className={styles.modalTitle}>Delete <strong>{item.name}</strong>?</p>
        <p className={styles.modalSub}>This cannot be undone.</p>
        <div className={styles.modalActions}>
          <button type="button" className={styles.modalCancel} onClick={onCancel}>Cancel</button>
          <button type="button" className={styles.modalDelete} onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  )
}
