import clsx from 'clsx'
import styles from './Card.module.css'

interface CardProps {
  title?: React.ReactNode
  actions?: React.ReactNode
  children?: React.ReactNode
  /** Hover lift + accent border for clickable cards */
  interactive?: boolean
  className?: string
  bodyClassName?: string
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void
}

export function Card({ title, actions, children, interactive = false, className, bodyClassName, onClick }: CardProps) {
  return (
    <div
      className={clsx(styles.card, interactive && styles.interactive, className)}
      onClick={onClick}
      {...(interactive ? { role: 'button', tabIndex: 0 } : {})}
    >
      {(title != null || actions != null) && (
        <div className={styles.header}>
          {title != null && <span className={styles.title}>{title}</span>}
          {actions != null && <div className={styles.actions}>{actions}</div>}
        </div>
      )}
      <div className={clsx(styles.body, bodyClassName)}>{children}</div>
    </div>
  )
}
