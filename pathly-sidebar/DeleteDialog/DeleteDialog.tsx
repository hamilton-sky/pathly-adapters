import { useEffect } from 'react'
import type { FileTreeController } from '../types'
import { KIND_LABEL } from '../lib/kinds'
import styles from './DeleteDialog.module.css'

interface Props {
  controller: FileTreeController
}

/** Confirmation modal shown before removing an item from the workspace. */
export function DeleteDialog({ controller }: Props): JSX.Element | null {
  const t = controller.deleteTarget
  useEffect(() => {
    if (!t) return
    const onKey = (e: KeyboardEvent) => {
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
        <h3 className={styles.title}>Delete {KIND_LABEL[t.kind]}</h3>
        <p className={styles.body}>
          Delete <strong className={styles.name}>{t.name}</strong> from the workspace?
        </p>
        <div className={styles.path}>/{t.path}</div>
        <p className={styles.warn}>This removes it from the pipeline. Cannot be undone.</p>
        <div className={styles.actions}>
          <button className={styles.cancel} onClick={controller.cancelDelete}>
            Cancel
          </button>
          <button className={styles.confirm} onClick={controller.confirmDelete}>
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
