import { useEffect, useRef } from 'react'
import { FileText, Folder } from 'lucide-react'
import styles from '../Sidebar.module.css'

interface Props {
  type: 'file' | 'folder'
  deep?: boolean
  dataLabel?: string
  onCommit: (name: string) => void
  onCancel: () => void
}

export function InlineCreateInput({ type, deep, dataLabel, onCommit, onCancel }: Props): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  function submit(): void {
    onCommit(inputRef.current?.value ?? '')
  }

  const rowStyle = deep ? { paddingLeft: 44 } : undefined

  return (
    <div className={styles.inlineCreateRow} style={rowStyle}>
      <span className={styles.inlineCreateIcon}>
        {type === 'folder' ? <Folder size={13} /> : <FileText size={13} />}
      </span>
      <input
        ref={inputRef}
        className={styles.inlineCreateInput}
        placeholder={type === 'folder' ? 'folder name…' : 'file name…'}
        data-label={dataLabel ?? (type === 'folder' ? 'New Folder Name' : 'New Plan Name')}
        defaultValue=""
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); submit() }
          if (e.key === 'Escape') { e.preventDefault(); onCancel() }
        }}
        onBlur={submit}
        spellCheck={false}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}
