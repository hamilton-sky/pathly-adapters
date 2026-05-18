import { useState } from 'react'
import { useTheme } from '../../useTheme'
import styles from './ui.module.css'

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
  const t = useTheme()
  const [hovered, setHovered] = useState(false)

  const padding = size === 'sm' ? '4px 10px' : '6px 14px'
  const fontSize = size === 'sm' ? '12px' : '13px'

  let background: string
  let color: string
  let border: string

  if (variant === 'primary') {
    background = hovered && !disabled ? t.accent + 'cc' : t.accent + '22'
    color = t.accent
    border = `1px solid ${t.accent}66`
  } else if (variant === 'destructive') {
    background = hovered && !disabled ? t.red + 'cc' : t.red + '22'
    color = t.red
    border = `1px solid ${t.red}66`
  } else {
    background = hovered && !disabled ? t.bgSurface0 : 'transparent'
    color = t.textSecondary
    border = `1px solid ${t.bgSurface1}`
  }

  const baseStyle: React.CSSProperties = {
    padding,
    fontSize,
    fontFamily: 'monospace',
    background,
    color,
    border,
    borderRadius: '5px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'background 0.12s, color 0.12s',
    ...style,
  }

  return (
    <button
      className={`pathly-btn ${styles.focusVisible}`}
      style={baseStyle}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {children}
    </button>
  )
}
