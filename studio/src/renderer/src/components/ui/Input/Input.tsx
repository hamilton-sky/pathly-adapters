import { useState } from 'react'
import clsx from 'clsx'
import styles from './Input.module.css'
import uiStyles from '../ui.module.css'

interface InputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
  autoFocus?: boolean
  /** Renders an uppercase label above the field */
  label?: string
  /** Leading icon inside the field */
  icon?: React.ReactNode
  size?: 'sm' | 'md'
  style?: React.CSSProperties
}

export function Input({
  value,
  onChange,
  placeholder,
  onKeyDown,
  autoFocus,
  label,
  icon,
  size = 'md',
  style,
}: InputProps): JSX.Element {
  const [focused, setFocused] = useState(false)

  return (
    <div className={styles.root} style={style}>
      {label != null && <span className={styles.label}>{label}</span>}
      <div
        className={clsx(
          'pathly-input',
          styles.wrap,
          styles[size],
          uiStyles.focusVisible,
          focused && styles.focused,
        )}
        data-focused={focused ? 'true' : undefined}
      >
        {icon != null && <span className={styles.icon}>{icon}</span>}
        <input
          className={styles.input}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          onKeyDown={onKeyDown}
          autoFocus={autoFocus}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        />
      </div>
    </div>
  )
}
