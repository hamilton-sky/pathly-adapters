import { useState } from 'react'
import { useTheme } from '../../useTheme'
import { Tooltip } from './Tooltip'
import styles from './ui.module.css'

interface IconButtonProps {
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  title: string
  description?: string
  shortcut?: string
  placement?: 'top' | 'bottom' | 'left' | 'right'
  children: React.ReactNode
  disabled?: boolean
  style?: React.CSSProperties
}

export function IconButton({
  onClick,
  title,
  description,
  shortcut,
  placement = 'bottom',
  children,
  disabled = false,
  style,
}: IconButtonProps): JSX.Element {
  const t = useTheme()
  const [hovered, setHovered] = useState(false)

  const baseStyle: React.CSSProperties = {
    width: '24px',
    height: '24px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: hovered && !disabled ? t.bgSurface0 : 'transparent',
    border: 'none',
    borderRadius: '4px',
    color: hovered && !disabled ? t.textPrimary : t.textSecondary,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    flexShrink: 0,
    transition: 'background var(--transition-base), color var(--transition-base)',
    padding: 0,
    ...style,
  }

  return (
    <Tooltip label={title} description={description} shortcut={shortcut} placement={placement}>
      <button
        className={`pathly-btn ${styles.focusVisible}`}
        style={baseStyle}
        disabled={disabled}
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        aria-label={title}
      >
        {children}
      </button>
    </Tooltip>
  )
}
