import { ReactNode } from 'react'
import styles from './Button.module.css'

type ButtonVariant = 'primary' | 'ghost' | 'quiet'

interface ButtonProps {
  children: ReactNode
  variant?: ButtonVariant
  icon?: ReactNode
  onClick?: () => void
  disabled?: boolean
}

/**
 * Footer action button.
 * - `primary` — accent fill (Apply)
 * - `ghost`   — surface card (Open in Notebook)
 * - `quiet`   — transparent outline (Cancel / Reset)
 */
export function Button({
  children,
  variant = 'quiet',
  icon,
  onClick,
  disabled,
}: ButtonProps): JSX.Element {
  return (
    <button
      type="button"
      className={`${styles.btn} ${styles[variant]}`}
      onClick={onClick}
      disabled={disabled}
    >
      {icon}
      {children}
    </button>
  )
}
