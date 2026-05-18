import { useState } from 'react'
import { useTheme } from '../../useTheme'
import styles from './ui.module.css'

interface InputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  autoFocus?: boolean
  style?: React.CSSProperties
}

export function Input({
  value,
  onChange,
  placeholder,
  onKeyDown,
  autoFocus,
  style,
}: InputProps): JSX.Element {
  const t = useTheme()
  const [focused, setFocused] = useState(false)

  const baseStyle: React.CSSProperties = {
    background: t.bgBase,
    border: `1px solid ${focused ? t.accent : t.bgSurface0}`,
    borderRadius: '6px',
    color: t.textPrimary,
    padding: '5px 9px',
    fontSize: '12px',
    fontFamily: 'monospace',
    transition: 'border-color 0.15s',
    width: '100%',
    boxSizing: 'border-box',
    ...style,
  }

  return (
    <input
      className={`pathly-input ${styles.focusVisible}`}
      style={baseStyle}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onKeyDown={onKeyDown}
      autoFocus={autoFocus}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    />
  )
}
