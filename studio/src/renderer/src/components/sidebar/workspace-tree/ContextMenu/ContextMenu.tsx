import { useEffect } from 'react'
import type { CSSProperties } from 'react'
import { ClipboardCopy, Code2, FilePlus, FolderPlus, LayoutGrid, Pencil, Trash2 } from 'lucide-react'
import type { WorkspaceTreeController } from '../types'
import { Tooltip } from '../../../ui/Tooltip/Tooltip'
import styles from './ContextMenu.module.css'

const MENU_W = 224
const MENU_H = 320

interface Props {
  controller: WorkspaceTreeController
}

/** Right-click / ⋯ dropdown — where every open/create/rename/delete action lives. */
export function ContextMenu({ controller }: Props): JSX.Element | null {
  const m = controller.menu
  useEffect(() => {
    if (!m) return
    const onKey = (e: KeyboardEvent): void => { if (e.key === 'Escape') controller.closeMenu() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [m, controller])

  if (!m) return null
  const { row } = m
  const left = Math.min(m.x, window.innerWidth - MENU_W)
  const top = Math.min(m.y, window.innerHeight - MENU_H)
  const pos = { '--menu-left': `${left}px`, '--menu-top': `${top}px` } as CSSProperties
  const hasOpenAction = !row.isFolder || row.isFeature
  const pathText = row.isRoot ? 'workspace root' : row.fsPath

  return (
    <>
      <div className={styles.scrim} onMouseDown={controller.closeMenu} onContextMenu={controller.closeMenu} />
      <div className={styles.menu} style={pos} role="menu">
        <Tooltip label={row.name} description={row.fsPath} placement="top">
          <div className={styles.header}>
            <div className={styles.headerText}>
              <span className={styles.headerName}>{row.name}</span>
              <span className={styles.headerPath}>{pathText}</span>
            </div>
          </div>
        </Tooltip>

        {!row.isFolder && (
          <button type="button" className={styles.item} onClick={() => controller.open(row)}>
            <Code2 size={15} /> Open
          </button>
        )}
        {row.isFeature && (
          <button type="button" className={styles.item} onClick={() => controller.openBoard(row)}>
            <LayoutGrid size={15} /> Open board
          </button>
        )}
        {hasOpenAction && <div className={styles.sep} />}

        {row.isFolder && (
          <>
            <button type="button" className={styles.item} onClick={() => controller.startCreate(row, 'file')}>
              <FilePlus size={15} /> New File
            </button>
            <button type="button" className={styles.item} onClick={() => controller.startCreate(row, 'folder')}>
              <FolderPlus size={15} /> New Folder
            </button>
            <div className={styles.sep} />
          </>
        )}

        <button type="button" className={styles.item} onClick={() => controller.copyPath(row)}>
          <ClipboardCopy size={15} /> Copy Path
        </button>

        {!row.isRoot && (
          <>
            <div className={styles.sep} />
            <button type="button" className={styles.item} onClick={() => controller.startRename(row)}>
              <Pencil size={15} /> Rename
            </button>
            <button type="button" className={`${styles.item} ${styles.danger}`} onClick={() => controller.askDelete(row)}>
              <Trash2 size={15} /> Delete
            </button>
          </>
        )}
      </div>
    </>
  )
}
