import { FileText, Pencil, Trash2 } from 'lucide-react'
import type { PathlyItem } from '../../types'
import { RenameInput } from './RenameInput'
import styles from './Sidebar.module.css'

interface Props {
  item: PathlyItem
  itemDir: string
  isSelected: boolean
  isDirty: boolean
  deep?: boolean
  renamingPath: string | null
  renameValue: string
  onSelect: () => void
  onRenameChange: (v: string) => void
  onRenameCommit: () => void
  onRenameCancel: () => void
  onStartRename: () => void
  onStartDelete: () => void
}

export function WorkspaceItem({
  item,
  isSelected,
  isDirty,
  deep,
  renamingPath,
  renameValue,
  onSelect,
  onRenameChange,
  onRenameCommit,
  onRenameCancel,
  onStartRename,
  onStartDelete,
}: Props): JSX.Element {
  const cls = [
    styles.itemRow,
    deep ? styles.itemRowDeep : '',
    isSelected ? styles.itemRowSelected : '',
  ].filter(Boolean).join(' ')

  return (
    <div
      className={cls}
      onClick={() => { if (renamingPath !== item.path) onSelect() }}
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect() }}
      title={item.path}
    >
      <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
      {renamingPath === item.path ? (
        <RenameInput
          value={renameValue}
          onChange={onRenameChange}
          onCommit={onRenameCommit}
          onCancel={onRenameCancel}
        />
      ) : (
        <>
          <span className={styles.itemName}>{item.name}</span>
          {isDirty && <span className={styles.dirtyDot}>●</span>}
          <div className={styles.rowActions}>
            <button
              className={styles.rowAction}
              title="Rename"
              onClick={(e) => { e.stopPropagation(); onStartRename() }}
            >
              <Pencil size={11} />
            </button>
            <button
              className={`${styles.rowAction} ${styles.rowActionDelete}`}
              title="Delete"
              onClick={(e) => { e.stopPropagation(); onStartDelete() }}
            >
              <Trash2 size={11} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
