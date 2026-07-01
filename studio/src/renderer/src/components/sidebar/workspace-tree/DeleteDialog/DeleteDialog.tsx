import { useEffect } from 'react'
import type { WorkspaceTreeController } from '../types'
import styles from './DeleteDialog.module.css'

interface Props {
  controller: WorkspaceTreeController
}

/** Confirmation modal shown before deleting a file/folder from disk. */
export function DeleteDialog({ controller }: Props): JSX.Element | null {
  const t = controller.deleteTarget
  useEffect(() => {
    if (!t) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') controller.cancelDelete()
      if (e.key === 'Enter') controller.confirmDelete()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [t, controller])

  if (!t) return null

  return (
    <div className={styles.backdrop} onMouseDown={controller.cancelDelete}>
      <div className={styles.dialog} onMouseDown={(e) => e.stopPropagation()}>
        <h3 className={styles.title}>Delete {t.isFolder ? 'folder' : 'file'}</h3>
        <p className={styles.body}>
          Delete <strong className={styles.name}>{t.name}</strong> from the workspace?
        </p>
        <div className={styles.path}>{t.fsPath}</div>
        <p className={styles.warn}>This permanently removes it from disk. Cannot be undone.</p>
        <div className={styles.actions}>
          <button type="button" className={styles.cancel} onClick={controller.cancelDelete}>Cancel</button>
          <button type="button" className={styles.confirm} onClick={controller.confirmDelete}>Delete</button>
        </div>
      </div>
    </div>
  )
}
