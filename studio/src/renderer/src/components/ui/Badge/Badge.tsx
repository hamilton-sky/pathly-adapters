import clsx from 'clsx'
import styles from './Badge.module.css'

export type BadgeVariant = 'core' | 'flow' | 'integration' | 'body' | 'neutral'

interface BadgeProps {
  label?: React.ReactNode
  children?: React.ReactNode
  variant?: BadgeVariant
  /** Any CSS color / token, e.g. "var(--green)". Overrides variant. */
  color?: string
  className?: string
}

export function Badge({ label, children, variant = 'neutral', color, className }: BadgeProps) {
  const style = color ? { '--badge-color': color } as React.CSSProperties : undefined
  return (
    <span
      className={clsx(styles.badge, !color && styles[variant], className)}
      style={style}
      data-variant={color ? 'custom' : variant}
    >
      {label ?? children}
    </span>
  )
}
