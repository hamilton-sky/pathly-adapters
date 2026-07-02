import { useEffect } from 'react'
import {
  ClipboardCopy,
  Code2,
  Copy,
  FilePlus,
  FolderPlus,
  Pencil,
  Trash2,
} from 'lucide-react'
import type { FileTreeController } from '../types'
import { KIND_COLOR } from '../lib/kinds'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './ContextMenu.module.css'

interface Props {
  controller: FileTreeController
}

const MENU_W = 224
const MENU_H = 300

/**
 * Right-click / ⋯ dropdown. Mirrors VS Code: kind-specific "open" action,
 * New File / New Folder on folders, Copy Path / Copy Relative Path, Rename,
 * Delete. Rendered only when `controller.menu` is set.
 */
export function ContextMenu({ controller }: Props): JSX.Element | null {
  const m = controller.menu
  useEffect(() => {
    if (!m) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') controller.closeMenu()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [m, controller])

  if (!m) return null

  const left = Math.min(m.x, window.innerWidth - MENU_W)
  const top = Math.min(m.y, window.innerHeight - MENU_H)
  const isFolderish = m.kind === 'folder' || m.kind === 'plan'
  const color = KIND_COLOR[m.kind]

  return (
    <>
      <div className={styles.scrim} onMouseDown={controller.closeMenu} onContextMenu={controller.closeMenu} />
      <div className={styles.menu} style={{ left, top }} role="menu">
        <div className={styles.header}>
          <span className={styles.headerIcon} style={{ color }}>
            {m.kind === 'file' ? <FileIcon color={color} /> : <FolderIcon open color={color} />}
          </span>
          <div className={styles.headerText}>
            <div className={styles.headerTitle}>
              <span className={styles.headerName}>{m.name}</span>
            </div>
            <span className={styles.headerPath}>{m.isRoot ? 'pathly/ · workspace root' : `/${m.path}`}</span>
          </div>
        </div>

        {m.kind === 'file' && (
          <>
            <button className={styles.item} onClick={() => controller.select(m.path)}>
              <Code2 size={15} /> Open in Editor
            </button>
            <div className={styles.sep} />
          </>
        )}

        {isFolderish && (
          <>
            <button className={styles.item} onClick={() => controller.startCreate(m.path, 'file')}>
              <FilePlus size={15} /> New File
            </button>
            <button className={styles.item} onClick={() => controller.startCreate(m.path, 'folder')}>
              <FolderPlus size={15} /> New Folder
            </button>
            <div className={styles.sep} />
          </>
        )}

        <button className={styles.item} onClick={() => controller.copyPath(m.path, m.isRoot)}>
          <Copy size={15} /> Copy Path
        </button>
        <button className={styles.item} onClick={() => controller.copyRelPath(m.path, m.isRoot)}>
          <ClipboardCopy size={15} /> Copy Relative Path
        </button>
        <div className={styles.sep} />

        <button className={styles.item} onClick={() => controller.startRename(m.path, m.name)}>
          <Pencil size={15} /> Rename
        </button>
        {!m.isRoot && (
          <button
            className={`${styles.item} ${styles.danger}`}
            onClick={() => controller.askDelete(m.path, m.name, m.kind)}
          >
            <Trash2 size={15} /> Delete
          </button>
        )}
      </div>
    </>
  )
}
