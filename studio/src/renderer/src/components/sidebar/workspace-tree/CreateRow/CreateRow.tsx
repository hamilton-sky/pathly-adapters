import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import type { WorkspaceTreeController, WsRow } from '../types'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './CreateRow.module.css'

interface Props {
  row: WsRow
  controller: WorkspaceTreeController
}

/** Inline "new file / new folder" input, rendered as a tree row. */
export function CreateRow({ row, controller }: Props): JSX.Element {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { ref.current?.focus() }, [])
  const indent = { '--level': row.level } as CSSProperties

  return (
    <div className={styles.row} style={indent}>
      <span className={styles.chevronSpace} />
      <span className={styles.icon}>
        {row.createType === 'folder' ? <FolderIcon open /> : <FileIcon />}
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
