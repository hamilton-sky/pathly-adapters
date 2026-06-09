import { FileText, GripVertical, Pencil, Trash2 } from 'lucide-react'
import type { PathlyItem } from '../../../types'
import { Tooltip } from '../../ui'
import { RenameInput } from '../shared/RenameInput'
import styles from '../Sidebar.module.css'

interface Props {
  item: PathlyItem
  isSelected: boolean
  isCanvasDraggable: boolean
  deep?: boolean
  onSelect: () => void
  onDragStart?: (e: React.DragEvent) => void
  onGripPointerDown?: () => void
  onStartRename?: () => void
  onStartDelete?: () => void
  renamingPath?: string | null
  renameValue?: string
  onRenameChange?: (v: string) => void
  onRenameCommit?: () => void
  onRenameCancel?: () => void
}

export function LibraryItem({ item, isSelected, isCanvasDraggable, deep, onSelect, onDragStart, onGripPointerDown, onStartRename, onStartDelete, renamingPath, renameValue, onRenameChange, onRenameCommit, onRenameCancel }: Props): JSX.Element {
  const isRenaming = renamingPath === item.path
  const cls = [
    styles.systemItemRow,
    deep ? styles.systemItemRowDeep : '',
    isSelected ? styles.systemItemRowSelected : '',
  ].filter(Boolean).join(' ')

  return (
    <div
      className={cls}
      draggable={isCanvasDraggable && !isRenaming}
      style={isCanvasDraggable && !isRenaming ? { cursor: 'grab' } : undefined}
      onClick={() => { if (!isRenaming) onSelect() }}
      onDragStart={onDragStart}
      title={item.path}
      tabIndex={0}
      onKeyDown={(e) => { if (!isRenaming && (e.key === 'Enter' || e.key === ' ')) onSelect() }}
    >
      {isCanvasDraggable && (
        <span
          className={styles.grip}
          onPointerDown={onGripPointerDown}
          title="Drag to canvas"
        >
          <GripVertical size={12} />
        </span>
      )}
      <FileText size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      {isRenaming && onRenameChange && onRenameCommit && onRenameCancel ? (
        <RenameInput
          value={renameValue ?? ''}
          onChange={onRenameChange}
          onCommit={onRenameCommit}
          onCancel={onRenameCancel}
        />
      ) : (
        <>
          <span className={styles.itemName}>{item.name}</span>
          {(onStartRename || onStartDelete) && (
            <div className={styles.rowActions}>
              {onStartRename && (
                <Tooltip label="Rename" placement="bottom">
                  <button
                    type="button"
                    className={styles.rowAction}
                    aria-label="Rename"
                    onClick={(e) => { e.stopPropagation(); onStartRename() }}
                  >
                    <Pencil size={11} />
                  </button>
                </Tooltip>
              )}
              {onStartDelete && (
                <Tooltip label="Delete" placement="bottom">
                  <button
                    type="button"
                    className={`${styles.rowAction} ${styles.rowActionDelete}`}
                    aria-label="Delete"
                    onClick={(e) => { e.stopPropagation(); onStartDelete() }}
                  >
                    <Trash2 size={11} />
                  </button>
                </Tooltip>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
