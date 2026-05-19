import { useEffect, useRef } from 'react'
import styles from './Sidebar.module.css'

interface Props {
  value: string
  onChange: (v: string) => void
  onCommit: () => void
  onCancel: () => void
}

export function RenameInput({ value, onChange, onCommit, onCancel }: Props): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.focus()
    el.select()
  }, [])
  return (
    <input
      ref={inputRef}
      className={styles.renameInput}
      value={value}
      aria-label="Rename file"
      placeholder="new name"
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') { e.preventDefault(); onCommit() }
        if (e.key === 'Escape') { e.preventDefault(); onCancel() }
      }}
      onBlur={onCommit}
      spellCheck={false}
      onClick={(e) => e.stopPropagation()}
    />
  )
}
