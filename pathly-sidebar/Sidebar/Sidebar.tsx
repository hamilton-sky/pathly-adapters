import { Activity, Database, FilePlus, FolderPlus, ListTree, Search, Settings } from 'lucide-react'
import type { FileTreeController } from '../types'
import { TreeRow } from '../TreeRow/TreeRow'
import { CreateRow } from '../CreateRow/CreateRow'
import { ContextMenu } from '../ContextMenu/ContextMenu'
import { DeleteDialog } from '../DeleteDialog/DeleteDialog'
import { Toast } from '../Toast/Toast'
import styles from './Sidebar.module.css'

interface Props {
  controller: FileTreeController
  /** Bottom-nav "N live" runtime count. */
  liveCount?: number
}

/**
 * Pathly workspace sidebar — file tree with animated icons (rotate-on-hover
 * files, open/close folders), inline create/rename, right-click + ⋯ context
 * menu, drag-and-drop into folders, filter, and collapse-all.
 *
 * All state lives in the {@link useFileTree} controller you pass in.
 */
export function Sidebar({ controller, liveCount = 2 }: Props): JSX.Element {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.headerLabel}>Workspace</span>
        <button className={styles.iconBtn} title="New file" onClick={() => controller.startCreate('', 'file')}>
          <FilePlus size={15} strokeWidth={2} />
        </button>
        <button className={styles.iconBtn} title="New folder" onClick={() => controller.startCreate('', 'folder')}>
          <FolderPlus size={15} strokeWidth={2} />
        </button>
        <button className={styles.iconBtn} title="Collapse all folders" onClick={controller.collapseAll}>
          <ListTree size={15} strokeWidth={2} />
        </button>
      </div>

      <div className={styles.filter}>
        <Search className={styles.filterIcon} size={13} strokeWidth={2} />
        <input
          className={styles.filterInput}
          value={controller.filter}
          placeholder="Search workspace (⌃P)"
          onChange={(e) => controller.setFilter(e.target.value)}
        />
      </div>

      <div className={styles.tree}>
        {controller.rows.map((row) =>
          row.isCreate ? (
            <CreateRow key={row.key} row={row} controller={controller} />
          ) : (
            <TreeRow key={row.key} row={row} controller={controller} />
          ),
        )}
      </div>

      <nav className={styles.nav}>
        <button className={styles.navItem}>
          <span className={styles.liveDot} />
          <span className={styles.navFlex}>Monitor</span>
          <span className={styles.liveCount}>{liveCount} live</span>
        </button>
        <button className={styles.navItem}>
          <Database size={15} strokeWidth={2} /> DB Explorer
        </button>
        <button className={styles.navItem}>
          <Settings size={15} strokeWidth={2} /> Settings
        </button>
      </nav>

      <ContextMenu controller={controller} />
      <DeleteDialog controller={controller} />
      <Toast message={controller.toast} />
    </aside>
  )
}
