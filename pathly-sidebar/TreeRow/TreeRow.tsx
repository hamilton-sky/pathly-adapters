import { useEffect, useRef } from 'react'
import {
  ChevronDown,
  ChevronRight,
  GitBranch,
  MoreHorizontal,
  Puzzle,
  Bot,
} from 'lucide-react'
import type { FileTreeController, FlatRow } from '../types'
import { KIND_COLOR } from '../lib/kinds'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './TreeRow.module.css'

interface Props {
  row: FlatRow
  controller: FileTreeController
}

/** One workspace row: chevron + kind icon + name (+ pill / inline actions). */
export function TreeRow({ row, controller }: Props): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (row.editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [row.editing])

  const color = KIND_COLOR[row.kind]
  const draggable = !row.isRoot && !row.editing
  const destFolder = row.isFolder ? row.path : row.parent

  function kindIcon(): JSX.Element {
    if (row.isFolder) return <FolderIcon open={row.open} color={color} />
    switch (row.kind) {
      case 'flow':
        return <GitBranch size={14} strokeWidth={2} style={{ color }} />
      case 'skill':
        return <Puzzle size={14} strokeWidth={2} style={{ color }} />
      case 'agent':
        return <Bot size={14} strokeWidth={2} style={{ color }} />
      default:
        return <FileIcon color={color} />
    }
  }

  return (
    <div
      data-pw-row
      className={[
        styles.row,
        row.isActive ? styles.active : '',
        row.isDragging ? styles.dragging : '',
        row.isDropTarget ? styles.dropTarget : '',
      ]
        .filter(Boolean)
        .join(' ')}
      draggable={draggable}
      onContextMenu={(e) => controller.openMenu(e, row.path, row.node, row.isRoot)}
      onDragStart={(e) => (row.isRoot ? undefined : controller.onDragStart(e, row.path))}
      onDragOver={(e) => controller.onDragOver(e, destFolder)}
      onDragLeave={(e) => controller.onDragLeave(e)}
      onDrop={(e) => controller.onDrop(e, destFolder)}
      onDragEnd={() => controller.onDragEnd()}
    >
      <button
        type="button"
        className={styles.button}
        style={{ paddingLeft: 10 + row.level * 14 }}
        onClick={() => (row.isFolder ? (row.isRoot ? undefined : controller.toggle(row.path)) : controller.select(row.path))}
      >
        <span className={styles.chevron}>
          {row.isFolder && !row.isRoot ? (
            row.open ? <ChevronDown size={13} strokeWidth={2.5} /> : <ChevronRight size={13} strokeWidth={2.5} />
          ) : null}
        </span>

        <span className={styles.icon}>{kindIcon()}</span>

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
          <>
            <span className={row.isFolder ? styles.folderName : styles.fileName}>{row.name}</span>
          </>
        )}
      </button>

      {!row.editing && (
        <span className={styles.actions}>
          <button
            type="button"
            className={styles.action}
            title="More actions"
            onClick={(e) => controller.openMenu(e, row.path, row.node, row.isRoot)}
          >
            <MoreHorizontal size={14} strokeWidth={2} />
          </button>
        </span>
      )}
    </div>
  )
}
