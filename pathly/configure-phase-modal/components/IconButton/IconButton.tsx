import { ReactNode } from 'react'
import styles from './IconButton.module.css'

interface IconButtonProps {
  icon: ReactNode
  children?: ReactNode
  onClick?: () => void
  /** Highlighted (e.g. while editing) — uses the warning accent. */
  active?: boolean
  'aria-label'?: string
}

/** Compact mono icon-plus-label button (edit / copy in the prompt header). */
export function IconButton({
  icon,
  children,
  onClick,
  active = false,
  ...rest
}: IconButtonProps): JSX.Element {
  return (
    <button
      type="button"
      className={`${styles.btn} ${active ? styles.active : ''}`}
      onClick={onClick}
      {...rest}
    >
      {icon}
      {children && <span>{children}</span>}
    </button>
  )
}
