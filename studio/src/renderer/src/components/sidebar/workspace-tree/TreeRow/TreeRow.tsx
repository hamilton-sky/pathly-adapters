import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { ChevronDown, ChevronRight, MoreHorizontal } from 'lucide-react'
import type { WorkspaceTreeController, WsRow } from '../types'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './TreeRow.module.css'

interface Props {
  row: WsRow
  controller: WorkspaceTreeController
}

/** One workspace row: chevron + folder/file icon + name (+ dirty dot / ⋯ actions). */
export function TreeRow({ row, controller }: Props): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (row.editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [row.editing])

  const destFolder = row.isFolder ? row.fsPath : row.parentFsPath
  const indent = { '--level': row.level } as CSSProperties

  return (
    <div
      data-ws-row="true"
      className={styles.row}
      {...(row.isActive ? { 'data-active': 'true' } : {})}
      {...(row.isRoot ? { 'data-root': 'true' } : {})}
      draggable={!row.isRoot && !row.editing}
      onContextMenu={(e) => controller.openMenu(e, row)}
      onDragStart={(e) => controller.onDragStart(e, row)}
      onDragOver={(e) => controller.onDragOver(e, destFolder)}
      onDragLeave={(e) => controller.onDragLeave(e)}
      onDrop={(e) => controller.onDrop(e, destFolder)}
      onDragEnd={() => controller.onDragEnd()}
    >
      <button
        type="button"
        className={styles.button}
        style={indent}
        onClick={() => (row.isFolder ? controller.toggle(row) : controller.select(row))}
        onDoubleClick={() => { if (!row.isFolder) controller.open(row) }}
      >
        <span className={styles.chevron}>
          {row.isFolder
            ? (row.open ? <ChevronDown size={13} strokeWidth={2.5} /> : <ChevronRight size={13} strokeWidth={2.5} />)
            : null}
        </span>

        <span className={styles.icon}>
          {row.isFolder ? <FolderIcon open={row.open} /> : <FileIcon />}
        </span>

        {row.editing ? (
          <input
            ref={inputRef}
            className={styles.rename}
            value={controller.editValue}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => controller.setEditValue(e.target.value)}
            onBlur={() => controller.submitRename()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') controller.submitRename()
              if (e.key === 'Escape') controller.cancelRename()
            }}
          />
        ) : (
          <span className={row.isFolder ? styles.folderName : styles.fileName}>{row.name}</span>
        )}

        {!row.editing && row.isDirty && <span className={styles.dirty} title="Unsaved changes">●</span>}
      </button>

      {!row.editing && !row.isRoot && (
        <span className={styles.actions}>
          <button
            type="button"
            className={styles.action}
            title="More actions"
            aria-label="More actions"
            onClick={(e) => controller.openMenu(e, row)}
          >
            <MoreHorizontal size={14} strokeWidth={2} />
          </button>
        </span>
      )}
    </div>
  )
}
