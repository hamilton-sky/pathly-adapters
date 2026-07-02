import { FileText } from 'lucide-react'
import styles from './FileIcon.module.css'

interface Props {
  size?: number
  color?: string
}

/**
 * File glyph — Pathly's lucide `FileText`. Spins a full turn when the row it
 * lives in is hovered (rows carry a `data-pw-row` attribute; the animation
 * rule lives in this component's own module so it stays self-contained).
 */
export function FileIcon({ size = 14, color = 'var(--text-muted)' }: Props): JSX.Element {
  return (
    <span className={styles.glyph} style={{ width: size, height: size, color }}>
      <FileText size={size} strokeWidth={2} />
    </span>
  )
}
