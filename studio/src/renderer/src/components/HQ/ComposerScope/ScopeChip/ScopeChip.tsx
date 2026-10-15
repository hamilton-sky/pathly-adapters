import { forwardRef, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import styles from './ScopeChip.module.css'

interface Props {
  icon: ReactNode
  label: string
  /** Compact count shown on the chip, e.g. "5/6". */
  count: string
  /** Spoken name, e.g. "Context: 5 of 6 board sections". */
  ariaLabel: string
  open: boolean
  /** id of the popover this chip opens. */
  controls: string
  onToggle: () => void
}

/** One chip in the composer row. Narrow rows collapse it to icon + count. */
export const ScopeChip = forwardRef<HTMLButtonElement, Props>(function ScopeChip(
  { icon, label, count, ariaLabel, open, controls, onToggle },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      className={styles.chip}
      data-open={open ? 'true' : 'false'}
      aria-haspopup="dialog"
      aria-controls={controls}
      aria-label={ariaLabel}
      title={ariaLabel}
      onClick={onToggle}
      {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
    >
      <span className={styles.icon} aria-hidden="true">{icon}</span>
      <span className={styles.label}>{label}</span>
      <span className={styles.count}>{count}</span>
      <ChevronDown size={10} className={styles.chevron} aria-hidden="true" />
    </button>
  )
})
