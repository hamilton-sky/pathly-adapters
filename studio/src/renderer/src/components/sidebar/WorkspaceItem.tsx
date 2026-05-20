import { useEffect, useRef, useState } from 'react'
import { FileText, Lock, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { useUiStore } from '../../store/uiStore'
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
  onStartRename?: () => void
  onStartDelete?: () => void
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
  const { userLockedPaths, toggleUserLock } = useUiStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const isUserLocked = userLockedPaths.has(item.path)
  // "actionable" = parent supplied at least one handler (not a system-protected file)
  const isActionable = Boolean(onStartRename ?? onStartDelete)

  useEffect(() => {
    if (!menuOpen) return
    function onOutside(e: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [menuOpen])

  const cls = [
    styles.itemRow,
    deep ? styles.itemRowDeep : '',
    isSelected ? styles.itemRowSelected : '',
  ].filter(Boolean).join(' ')

  function handleMenuAction(action: () => void): void {
    setMenuOpen(false)
    action()
  }

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

          {/* User-locked: show clickable lock to unlock */}
          {isActionable && isUserLocked && (
            <div className={`${styles.rowActions} ${styles.rowActionsLocked}`}>
              <button
                className={`${styles.rowAction} ${styles.rowActionLock}`}
                title="Locked — click to unlock"
                onClick={(e) => { e.stopPropagation(); toggleUserLock(item.path) }}
              >
                <Lock size={11} />
              </button>
            </div>
          )}

          {/* Normal: show ⋯ on hover → popover */}
          {isActionable && !isUserLocked && (
            <div className={styles.rowActions}>
              <button
                className={styles.rowAction}
                title="Actions"
                onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
              >
                <MoreHorizontal size={13} />
              </button>

              {menuOpen && (
                <div className={styles.itemMenu} ref={menuRef}>
                  {onStartRename && (
                    <button
                      className={styles.itemMenuItem}
                      onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartRename) }}
                    >
                      <Pencil size={12} />
                      Rename
                    </button>
                  )}
                  {onStartDelete && (
                    <button
                      className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`}
                      onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartDelete) }}
                    >
                      <Trash2 size={12} />
                      Delete
                    </button>
                  )}
                  <div className={styles.itemMenuSep} />
                  <button
                    className={styles.itemMenuItem}
                    onClick={(e) => { e.stopPropagation(); toggleUserLock(item.path); setMenuOpen(false) }}
                  >
                    <Lock size={12} />
                    Lock file
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
