import { MoreHorizontal } from 'lucide-react'
import type { WorkspaceTreeController, WsRow } from '../types'
import { FileIcon } from '../FileIcon/FileIcon'
import { FolderIcon } from '../FolderIcon/FolderIcon'
import styles from './ResultRow.module.css'

interface Props {
  row: WsRow
  /** Containing directory relative to the project root (shown muted under the name). */
  relDir: string
  controller: WorkspaceTreeController
}

/** One flat search result: icon + name over its relative path (list view). */
export function ResultRow({ row, relDir, controller }: Props): JSX.Element {
  return (
    <div
      data-ws-row="true"
      className={styles.row}
      {...(row.isActive ? { 'data-active': 'true' } : {})}
      onContextMenu={(e) => controller.openMenu(e, row)}
    >
      <button
        type="button"
        className={styles.button}
        title={row.fsPath}
        onClick={() => controller.select(row)}
        onDoubleClick={() => controller.open(row)}
      >
        <span className={styles.icon}>{row.isFolder ? <FolderIcon /> : <FileIcon />}</span>
        <span className={styles.text}>
          <span className={styles.name}>{row.name}</span>
          {relDir && <span className={styles.dir}>{relDir}</span>}
        </span>
      </button>
      <span className={styles.actions}>
        <button
          type="button"
          className={styles.action}
          aria-label="More actions"
          onClick={(e) => controller.openMenu(e, row)}
        >
          <MoreHorizontal size={14} strokeWidth={2} />
        </button>
      </span>
    </div>
  )
}
