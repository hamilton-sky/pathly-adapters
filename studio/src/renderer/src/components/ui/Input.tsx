import clsx from 'clsx'
import styles from './Input.module.css'
import uiStyles from './ui.module.css'

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
  return (
    <input
      className={clsx('pathly-input', styles.input, uiStyles.focusVisible)}
      style={style}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onKeyDown={onKeyDown}
      autoFocus={autoFocus}
    />
  )
}
