import { useEffect, useRef, useState } from 'react'
import { FolderOpen } from 'lucide-react'
import styles from './Sidebar.module.css'

interface Props {
  onConfirm: (name: string) => void
  onCancel: () => void
}

export function InlineFolderInput({ onConfirm, onCancel }: Props): JSX.Element {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { inputRef.current?.focus() }, [])
  return (
    <div className={styles.inlineCreateRow}>
      <FolderOpen size={13} className={styles.inlineCreateIcon} />
      <input
        ref={inputRef}
        className={styles.inlineCreateInput}
        value={value}
        aria-label="Folder name"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); onConfirm(value) }
          if (e.key === 'Escape') { e.preventDefault(); onCancel() }
        }}
        onBlur={() => onConfirm(value)}
        placeholder="folder name"
        spellCheck={false}
      />
    </div>
  )
}
