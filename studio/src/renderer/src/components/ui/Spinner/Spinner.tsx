import clsx from 'clsx'
import styles from './Spinner.module.css'

interface SpinnerProps {
  /** px. @default 14 */
  size?: number
  /** Arc color token. @default "var(--accent)" */
  color?: string
  className?: string
}

export function Spinner({ size = 14, color = 'var(--accent)', className }: SpinnerProps) {
  return (
    <span
      className={clsx(styles.spinner, className)}
      style={{ '--sp-size': `${size}px`, '--sp-color': color } as React.CSSProperties}
      aria-label="Loading"
    />
  )
}
