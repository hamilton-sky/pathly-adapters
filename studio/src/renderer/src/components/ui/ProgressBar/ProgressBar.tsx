import clsx from 'clsx'
import styles from './ProgressBar.module.css'

interface ProgressBarProps {
  value: number
  max?: number
  /** Fill color token. @default "var(--accent)" */
  color?: string
  /** Track height in px. @default 6 */
  height?: number
  /** Trailing label e.g. "3/3" */
  label?: React.ReactNode
  className?: string
}

function ProgressBar({ value, max = 100, color = 'var(--accent)', height = 6, label, className }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={clsx(styles.wrap, className)}>
      <div
        className={styles.track}
        style={{ '--pb-height': `${height}px` } as React.CSSProperties}
      >
        <div
          className={styles.fill}
          style={{ '--pb-pct': `${pct}%`, '--pb-color': color } as React.CSSProperties}
        />
      </div>
      {label != null && <span className={styles.label}>{label}</span>}
    </div>
  )
}
