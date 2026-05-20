import { useRef, useState } from 'react'
import { FileText, Lock, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
import type { PathlyItem, PathlyReorgDragItem, PathlySection } from '../../types'
import { PATHLY_DRAG_MIME } from '../../types'
import { RenameInput } from './RenameInput'
import { ContextMenu } from './ContextMenu'
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
  onStartRename?: () => void
  onStartDelete?: () => void
  sidebarWidth?: number
  sectionId?: string
  isProtectedFile?: boolean
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
  sidebarWidth,
  sectionId,
  isProtectedFile,
}: Props): JSX.Element {
  const { userLockedPaths, toggleUserLock } = useUiStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)

  const isUserLocked = userLockedPaths.has(item.path)
  // "actionable" = parent supplied at least one handler (not a system-protected file)
  const isActionable = Boolean(onStartRename ?? onStartDelete)

  const cls = [
    styles.itemRow,
    deep ? styles.itemRowDeep : '',
    isSelected ? styles.itemRowSelected : '',
    !isProtectedFile ? styles.draggableItem : '',
  ].filter(Boolean).join(' ')

  function handleMenuAction(action: () => void): void {
    setMenuOpen(false)
    action()
  }

  return (
    <div
      ref={rowRef}
      className={cls}
      draggable={!isProtectedFile && renamingPath !== item.path}
      onDragStart={(e) => {
        if (isProtectedFile) { e.preventDefault(); return }
        const payload: PathlyReorgDragItem = {
          dragType: 'reorg',
          name: item.name,
          section: (sectionId ?? 'skills') as PathlySection,
          path: [item.name],
          type: 'file',
          sourcePath: item.path,
        }
        e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
        e.dataTransfer.effectAllowed = 'move'
      }}
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

          {isActionable && (
            <div className={styles.rowActions}>
              {isUserLocked && (
                <span className={`${styles.rowAction} ${styles.rowActionLock}`} title="Locked — delete disabled">
                  <Lock size={11} />
                </span>
              )}
              <button
                className={styles.rowAction}
                title="Actions"
                onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
              >
                <MoreHorizontal size={13} />
              </button>

              {menuOpen && rowRef.current && (
                <ContextMenu
                  anchor={rowRef.current.getBoundingClientRect()}
                  sidebarWidth={sidebarWidth ?? parseInt(localStorage.getItem('sidebar-width') ?? '240', 10)}
                  onClose={() => setMenuOpen(false)}
                >
                  {onStartRename && (
                    <button className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartRename) }}>
                      <Pencil size={12} />
                      Rename
                    </button>
                  )}
                  {!isUserLocked && onStartDelete && (
                    <button className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`} onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartDelete) }}>
                      <Trash2 size={12} />
                      Delete
                    </button>
                  )}
                  <div className={styles.itemMenuSep} />
                  <button className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); toggleUserLock(item.path); setMenuOpen(false) }}>
                    <Lock size={12} />
                    {isUserLocked ? 'Unlock file' : 'Lock file'}
                  </button>
                </ContextMenu>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
