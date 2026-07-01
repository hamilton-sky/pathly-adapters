import { FileText } from 'lucide-react'
import styles from './FileIcon.module.css'

/** File glyph — spins a full turn when its row (`data-ws-row`) is hovered. */
export function FileIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <span className={styles.glyph}>
      <FileText size={size} strokeWidth={2} />
    </span>
  )
}
