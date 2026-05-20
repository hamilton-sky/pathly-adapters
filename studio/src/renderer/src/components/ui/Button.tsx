import clsx from 'clsx'
import styles from './Button.module.css'
import uiStyles from './ui.module.css'

type Variant = 'primary' | 'ghost' | 'destructive'
type Size = 'sm' | 'md'

interface ButtonProps {
  variant?: Variant
  size?: Size
  disabled?: boolean
  onClick?: () => void
  children: React.ReactNode
  style?: React.CSSProperties
}

export function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  onClick,
  children,
  style,
}: ButtonProps): JSX.Element {
  return (
    <button
      className={clsx('pathly-btn', styles.btn, styles[variant], styles[size], uiStyles.focusVisible)}
      style={style}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
