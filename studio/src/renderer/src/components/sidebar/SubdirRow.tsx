import { useRef, useEffect, useState } from 'react'
import { ChevronRight, ChevronDown, Folder, Lock, MoreHorizontal } from 'lucide-react'
import styles from './Sidebar.module.css'

interface Props {
  name: string
  open: boolean
  onToggle: () => void
  isSystemFolder?: boolean
  isUserLocked?: boolean
  onToggleFolderLock?: () => void
  onStartDeleteFolder?: () => void // wired in Conv 4
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
  isDragOver,
  onDragOver,
  onDrop,
  onDragLeave,
}: Props): JSX.Element {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    function onOutside(e: MouseEvent): void {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    function onEscape(e: KeyboardEvent): void {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onOutside)
      document.removeEventListener('keydown', onEscape)
    }
  }, [menuOpen])

  return (
    <div
      className={`${styles.subdirHeader}${isDragOver ? ` ${styles.subdirRowDragOver}` : ''}`}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onToggle() }}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; onDragOver?.(e) }}
      onDrop={(e) => { e.preventDefault(); onDrop?.(e) }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) onDragLeave?.() }}
    >
      <span className={styles.chevron}>
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
      </span>
      <Folder size={13} className={styles.subdirFolderIcon} />
      <span className={styles.subdirLabel}>{name}/</span>

      {isSystemFolder && (
        <div className={`${styles.rowActions} ${styles.rowActionsLocked}`}>
          <span
            className={`${styles.rowAction} ${styles.systemLockIcon}`}
            title="Managed by Pathly"
          >
            <Lock size={11} />
          </span>
        </div>
      )}

      {isUserLocked && !isSystemFolder && (
        <div className={`${styles.rowActions} ${styles.rowActionsLocked}`}>
          <button
            className={`${styles.rowAction} ${styles.rowActionLock}`}
            title="Locked — click to unlock"
            onClick={(e) => { e.stopPropagation(); onToggleFolderLock?.() }}
          >
            <Lock size={11} />
          </button>
        </div>
      )}

      {!isSystemFolder && !isUserLocked && (
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
              <button
                className={styles.itemMenuItem}
                onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onToggleFolderLock?.() }}
              >
                <Lock size={12} />
                Lock folder
              </button>
              {onStartDeleteFolder && (
                <>
                  <div className={styles.itemMenuSep} />
                  <button
                    className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`}
                    onClick={(e) => { e.stopPropagation(); setMenuOpen(false); onStartDeleteFolder() }}
                  >
                    Delete folder
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
