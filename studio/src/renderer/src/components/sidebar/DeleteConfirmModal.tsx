import type { PathlyItem } from '../../types'
import styles from './Sidebar.module.css'

interface Props {
  item: PathlyItem
  onCancel: () => void
  onConfirm: () => void
}

export function DeleteConfirmModal({ item, onCancel, onConfirm }: Props): JSX.Element {
  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modalBox}>
        <p className={styles.modalTitle}>Delete <strong>{item.name}</strong>?</p>
        <p className={styles.modalSub}>This cannot be undone.</p>
        <div className={styles.modalActions}>
          <button className={styles.modalCancel} onClick={onCancel}>Cancel</button>
          <button className={styles.modalDelete} onClick={onConfirm}>Delete</button>
        </div>
      </div>
    </div>
  )
}
