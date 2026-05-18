import { useState } from 'react'
import { useTheme } from '../../useTheme'

interface IconButtonProps {
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  title: string
  children: React.ReactNode
  disabled?: boolean
  style?: React.CSSProperties
}

export function IconButton({
  onClick,
  title,
  children,
  disabled = false,
  style,
}: IconButtonProps): JSX.Element {
  const t = useTheme()
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)

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
    transition: 'background 0.12s, color 0.12s',
    outline: focused ? `2px solid ${t.accent}` : 'none',
    outlineOffset: '2px',
    padding: 0,
    ...style,
  }

  return (
    <button
      style={baseStyle}
      title={title}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    >
      {children}
    </button>
  )
}
