import { Folder, FolderOpen } from 'lucide-react'
import styles from './FolderIcon.module.css'

interface Props {
  /** Expanded folders render open; collapsed render closed. */
  open?: boolean
  size?: number
  color?: string
}

/**
 * Folder glyph with an open/close animation. Lucide `Folder` and `FolderOpen`
 * are stacked and cross-faded: the folder "opens" when its row is hovered
 * (`data-pw-row`), and stays open while the folder is expanded (`open`).
 */
export function FolderIcon({ open = false, size = 15, color = 'var(--accent)' }: Props): JSX.Element {
  return (
    <span
      className={`${styles.wrap} ${open ? styles.isOpen : ''}`}
      style={{ width: size, height: size, color }}
    >
      <Folder className={styles.closed} size={size} strokeWidth={2} />
      <FolderOpen className={styles.open} size={size} strokeWidth={2} />
    </span>
  )
}
