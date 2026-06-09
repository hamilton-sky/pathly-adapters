import { useRef, useState } from 'react'
import { ChevronRight, ChevronDown, FilePlus, FolderPlus, Folder, FolderOpen, GripVertical, Lock, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { RenameInput } from '../shared/RenameInput'
import { ContextMenu } from '../shared/ContextMenu'
import styles from '../Sidebar.module.css'

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
  onCreateFolderInFolder?: () => void
  renamingThis?: boolean
  renameValue?: string
  onRenameChange?: (v: string) => void
  onRenameCommit?: () => void
  onRenameCancel?: () => void
  folderPath?: string
  onFolderDragStart?: (e: React.DragEvent) => void
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
  onCreateFolderInFolder,
  renamingThis,
  renameValue,
  onRenameChange,
  onRenameCommit,
  onRenameCancel,
  onFolderDragStart,
  isDragOver,
  onDragOver,
  onDrop,
  onDragLeave,
}: Props): JSX.Element {
  const [menuOpen, setMenuOpen] = useState(false)
  const rowRef = useRef<HTMLDivElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  return (
    <div
      ref={rowRef}
      className={`${styles.subdirHeader}${isDragOver ? ` ${styles.subdirRowDragOver}` : ''}`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      draggable={!isSystemFolder && !isUserLocked && !renamingThis && Boolean(onFolderDragStart)}
      onDragStart={(e) => { if (!isSystemFolder && !isUserLocked && !renamingThis) onFolderDragStart?.(e) }}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; onDragOver?.(e) }}
      onDrop={(e) => { e.preventDefault(); onDrop?.(e) }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) onDragLeave?.() }}
    >
      <span className={styles.chevron}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </span>
      {open
        ? <FolderOpen size={15} className={styles.subdirFolderIcon} />
        : <Folder size={15} className={styles.subdirFolderIcon} />
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
            <span className={`${styles.rowAction} ${styles.rowActionLock}`} title="Locked â€” delete disabled">
              <Lock size={11} />
            </span>
          )}
          {onFolderDragStart && !isUserLocked && !isSystemFolder && (
            <span className={`${styles.rowAction} ${styles.grip}`} title="Drag to move folder">
              <GripVertical size={12} />
            </span>
          )}
          <button
            ref={menuButtonRef}
            className={styles.rowAction}
            title="Actions"
            onClick={(e) => { e.stopPropagation(); setMenuOpen(v => !v) }}
          >
            <MoreHorizontal size={15} />
          </button>

          {menuOpen && menuButtonRef.current && (
            <ContextMenu
              anchor={menuButtonRef.current.getBoundingClientRect()}
              onClose={() => setMenuOpen(false)}
            >
              {onCreateFolderInFolder && (
                <button
                  className={styles.itemMenuItem}
                  onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onCreateFolderInFolder() }}
                >
                  <FolderPlus size={12} />
                  New folder
                </button>
              )}
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
