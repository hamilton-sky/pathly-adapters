import { useEffect, useRef } from 'react'
import type { FileTreeController, FlatRow } from '../types'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './CreateRow.module.css'

interface Props {
  row: FlatRow
  controller: FileTreeController
}

/** Inline "new file / new folder" input, rendered as a tree row. */
export function CreateRow({ row, controller }: Props): JSX.Element {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    ref.current?.focus()
  }, [])

  return (
    <div className={styles.row} style={{ paddingLeft: 10 + row.level * 14 }}>
      <span className={styles.chevronSpace} />
      <span className={styles.icon}>
        {row.createType === 'folder' ? (
          <FolderIcon open color="var(--accent)" />
        ) : (
          <FileIcon color="var(--text-muted)" />
        )}
      </span>
      <input
        ref={ref}
        className={styles.input}
        value={controller.createValue}
        placeholder={controller.createPlaceholder}
        onChange={(e) => controller.setCreateValue(e.target.value)}
        onBlur={() => controller.submitCreate()}
        onKeyDown={(e) => {
          if (e.key === 'Enter') controller.submitCreate()
          if (e.key === 'Escape') controller.cancelCreate()
        }}
      />
    </div>
  )
}
