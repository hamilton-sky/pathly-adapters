import { useRef, useState } from 'react'
import { ChevronRight, ChevronDown, FilePlus, Folder, FolderOpen, GripVertical, Lock, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { RenameInput } from './RenameInput'
import { ContextMenu } from './ContextMenu'
import styles from './Sidebar.module.css'

interface Props {
  name: string
  open: boolean
  onToggle: () => void
  isSystemFolder?: boolean
  isUserLocked?: boolean
  onToggleFolderLock?: () => void
  onStartDeleteFolder?: () => void
  onStartRenameFolder?: () => void
  onCreateFileInFolder?: () => void
  onFolderDragStart?: (e: React.DragEvent) => void
  renamingThis?: boolean
  renameValue?: string
  onRenameChange?: (v: string) => void
  onRenameCommit?: () => void
  onRenameCancel?: () => void
  folderPath?: string
  isDragOver?: boolean
  onDragOver?: (e: React.DragEvent) => void
  onDrop?: (e: React.DragEvent) => void
  onDragLeave?: () => void
}

export function SubdirRow({
  name,
  open,
  onToggle,
  isSystemFolder,
  isUserLocked,
  onToggleFolderLock,
  onStartDeleteFolder,
  onStartRenameFolder,
  onCreateFileInFolder,
  onFolderDragStart,
  renamingThis,
  renameValue,
  onRenameChange,
  onRenameCommit,
  onRenameCancel,
  isDragOver,
  onDragOver,
  onDrop,
  onDragLeave,
}: Props): JSX.Element {
  const [menuOpen, setMenuOpen] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)

  const sidebarWidth = parseInt(localStorage.getItem('sidebar-width') ?? '240', 10)

  return (
    <div
      ref={rowRef}
      className={`${styles.subdirHeader}${isDragOver ? ` ${styles.subdirRowDragOver}` : ''}`}
      draggable={!isSystemFolder && !renamingThis && Boolean(onFolderDragStart)}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      onDragStart={(e) => { if (!isSystemFolder && !renamingThis) onFolderDragStart?.(e) }}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; onDragOver?.(e) }}
      onDrop={(e) => { e.preventDefault(); onDrop?.(e) }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) onDragLeave?.() }}
    >
      <span className={styles.chevron}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </span>
      {open
        ? <FolderOpen size={13} className={styles.subdirFolderIcon} />
        : <Folder size={13} className={styles.subdirFolderIcon} />
      }

      {renamingThis ? (
        <RenameInput
          value={renameValue ?? ''}
          onChange={(v) => onRenameChange?.(v)}
          onCommit={() => onRenameCommit?.()}
          onCancel={() => onRenameCancel?.()}
        />
      ) : (
        <span className={styles.subdirLabel}>{name}/</span>
      )}

      {isSystemFolder ? (
        <div className={`${styles.rowActions} ${styles.rowActionsLocked}`}>
          <span
            className={`${styles.rowAction} ${styles.systemLockIcon}`}
            title="Managed by Pathly"
          >
            <Lock size={11} />
          </span>
        </div>
      ) : !renamingThis ? (
        <div className={styles.rowActions}>
          {isUserLocked && (
            <span className={`${styles.rowAction} ${styles.rowActionLock}`} title="Locked — delete disabled">
              <Lock size={11} />
            </span>
          )}
          {onFolderDragStart && (
            <span className={`${styles.rowAction} ${styles.grip}`} title="Drag to move folder">
              <GripVertical size={12} />
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
              sidebarWidth={sidebarWidth}
              onClose={() => setMenuOpen(false)}
            >
              {onCreateFileInFolder && (
                <button
                  className={styles.itemMenuItem}
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onCreateFileInFolder() }}
                >
                  <FilePlus size={12} />
                  New file
                </button>
              )}
              {onStartRenameFolder && (
                <button
                  className={styles.itemMenuItem}
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onStartRenameFolder() }}
                >
                  <Pencil size={12} />
                  Rename
                </button>
              )}
              <button
                className={styles.itemMenuItem}
                onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onToggleFolderLock?.() }}
              >
                <Lock size={12} />
                {isUserLocked ? 'Unlock folder' : 'Lock folder'}
              </button>
              {!isUserLocked && onStartDeleteFolder && (
                <>
                  <div className={styles.itemMenuSep} />
                  <button
                    className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`}
                    onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onStartDeleteFolder() }}
                  >
                    <Trash2 size={12} />
                    Delete folder
                  </button>
                </>
              )}
            </ContextMenu>
          )}
        </div>
      ) : null}
    </div>
  )
}
