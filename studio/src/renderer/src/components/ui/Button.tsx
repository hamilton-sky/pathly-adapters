import clsx from 'clsx'
import styles from './Button.module.css'
import uiStyles from './ui.module.css'

type Variant = 'primary' | 'ghost' | 'destructive'
type Size = 'sm' | 'md'

interface ButtonProps {
  variant?: Variant
  size?: Size
  disabled?: boolean
  loading?: boolean
  onClick?: () => void
  children: React.ReactNode
  style?: React.CSSProperties
  'data-testid'?: string
}

export function Button({
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  children,
  style,
  'data-testid': dataTestId,
}: ButtonProps): JSX.Element {
  return (
    <button
      className={clsx('pathly-btn', styles.btn, styles[variant], styles[size], uiStyles.focusVisible, loading && styles.loading)}
      style={style}
      disabled={disabled || loading}
      onClick={onClick}
      data-testid={dataTestId}
    >
      {children}
    </button>
  )
}
