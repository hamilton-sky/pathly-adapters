import { Folder, FolderOpen } from 'lucide-react'
import styles from './FolderIcon.module.css'

/** Folder glyph — cross-fades open/closed on expand and on row hover. */
export function FolderIcon({ open = false, size = 15 }: { open?: boolean; size?: number }): JSX.Element {
  return (
    <span className={`${styles.wrap} ${open ? styles.isOpen : ''}`}>
      <Folder className={styles.closed} size={size} strokeWidth={2} />
      <FolderOpen className={styles.open} size={size} strokeWidth={2} />
    </span>
  )
}
