import { ReactNode } from 'react'
import styles from './Chip.module.css'
import type { ChipVariant } from '../../types'

interface ChipProps {
  children: ReactNode
  /** Selection group — sets the active accent colour. */
  variant?: ChipVariant
  selected?: boolean
  /** Render in the mono type style (agents / skills). */
  mono?: boolean
  onClick?: () => void
}

/** Selectable pill. Shows a leading dot + group-coloured fill when selected. */
export function Chip({
  children,
  variant = 'host',
  selected = false,
  mono = false,
  onClick,
}: ChipProps): JSX.Element {
  const className = [
    styles.chip,
    mono && styles.mono,
    selected && styles.selected,
    selected && styles[variant],
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type="button" className={className} onClick={onClick} aria-pressed={selected}>
      {selected && <span className={styles.dot} />}
      {children}
    </button>
  )
}
