import { useRef, useState } from 'react'
import { FileText, Lock, MoreHorizontal, Pencil, Plus, Scissors, Trash2 } from 'lucide-react'
import { useUiStore } from '../../../store/uiStore'
import type { PathlyItem, PathlyReorgDragItem, PathlySection } from '../../../types'
import { PATHLY_DRAG_MIME } from '../../../types'
import { Tooltip } from '../../ui'
import { RenameInput } from '../shared/RenameInput'
import { ContextMenu } from '../shared/ContextMenu'
import styles from '../Sidebar.module.css'

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
  onSplitIntoCells?: () => void
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
  onSplitIntoCells,
  sectionId,
  isProtectedFile,
}: Props): JSX.Element {
  const { userLockedPaths, toggleUserLock, activePanel } = useUiStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

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
      onClick={() => { if (renamingPath !== item.path) onSelect() }}
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect() }}
      title={item.path}
      draggable={!isProtectedFile && !isUserLocked && renamingPath !== item.path}
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
    >
      <FileText size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

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
          {isDirty && <span className={styles.dirtyDot}>â—</span>}

          {isActionable && (
            <div className={styles.rowActions}>
              {isUserLocked && (
                <Tooltip label="Locked — delete disabled" placement="bottom">
                  <span className={`${styles.rowAction} ${styles.rowActionLock}`}>
                    <Lock size={11} />
                  </span>
                </Tooltip>
              )}
              <Tooltip label="Actions" placement="bottom">
                <button
                  type="button"
                  ref={menuButtonRef}
                  className={styles.rowAction}
                  aria-label="Actions"
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
                >
                  <MoreHorizontal size={15} />
                </button>
              </Tooltip>

              {menuOpen && menuButtonRef.current && (
                <ContextMenu
                  anchor={menuButtonRef.current.getBoundingClientRect()}
                  onClose={() => setMenuOpen(false)}
                >
                  {activePanel === 'skill-notebook' && item.name.endsWith('.md') && onSplitIntoCells && (
                    <>
                      <button type="button" className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); handleMenuAction(onSplitIntoCells) }}>
                        <Plus size={12} />
                        Insert as cell
                      </button>
                      <button type="button" className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); handleMenuAction(onSplitIntoCells) }}>
                        <Scissors size={12} />
                        Split into cells
                      </button>
                      {(onStartRename ?? onStartDelete) && <div className={styles.itemMenuSep} />}
                    </>
                  )}
                  {onStartRename && !isUserLocked && (
                    <button type="button" className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartRename) }}>
                      <Pencil size={12} />
                      Rename
                    </button>
                  )}
                  {!isUserLocked && onStartDelete && (
                    <button type="button" className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`} onClick={(e) => { e.stopPropagation(); handleMenuAction(onStartDelete) }}>
                      <Trash2 size={12} />
                      Delete
                    </button>
                  )}
                  <div className={styles.itemMenuSep} />
                  <button type="button" className={styles.itemMenuItem} onClick={(e) => { e.stopPropagation(); toggleUserLock(item.path); setMenuOpen(false) }}>
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
