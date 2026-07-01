import { FilePlus, FolderPlus, ListTree, Search } from 'lucide-react'
import { useWorkspaceTree } from './useWorkspaceTree'
import { TreeRow } from './TreeRow/TreeRow'
import { CreateRow } from './CreateRow/CreateRow'
import { ContextMenu } from './ContextMenu/ContextMenu'
import { DeleteDialog } from './DeleteDialog/DeleteDialog'
import { Toast } from './Toast/Toast'
import type { WorkspaceTreeController, WsRow } from './types'
import styles from './WorkspaceTree.module.css'

function renderRow(row: WsRow, controller: WorkspaceTreeController): JSX.Element {
  return row.isCreate
    ? <CreateRow key={row.key} row={row} controller={controller} />
    : <TreeRow key={row.key} row={row} controller={controller} />
}

/** The Workspace tab body — a plain, real project file tree (+ pinned pathly/). */
export function WorkspaceTree(): JSX.Element {
  const { controller } = useWorkspaceTree()
  const rootRow = controller.rows[0]
  const scope = controller.searchScope
  const searching = controller.filter.trim().length > 0
  const showPinned = controller.pinnedRows.length > 0 && (!searching || scope === 'pathly')
  const showMain = !searching || scope === 'project'

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <Search className={styles.searchIcon} size={13} strokeWidth={2} />
          <input
            className={styles.searchInput}
            value={controller.filter}
            placeholder="Search workspace"
            onChange={(e) => controller.setFilter(e.target.value)}
          />
          <button
            type="button"
            className={styles.scopeChip}
            {...(scope === 'pathly' ? { 'data-scope': 'pathly' } : {})}
            title={scope === 'pathly'
              ? 'Searching pathly/ only — click to search the whole project'
              : 'Searching the whole project — click to search pathly/ only'}
            onClick={() => controller.setSearchScope(scope === 'pathly' ? 'project' : 'pathly')}
          >
            {scope === 'pathly' ? 'pathly' : 'All'}
          </button>
        </div>
        <button
          type="button" className={styles.iconBtn} title="New file in project root" aria-label="New file"
          disabled={!rootRow} onClick={() => { if (rootRow) controller.startCreate(rootRow, 'file') }}
        >
          <FilePlus size={15} strokeWidth={2} />
        </button>
        <button
          type="button" className={styles.iconBtn} title="New folder in project root" aria-label="New folder"
          disabled={!rootRow} onClick={() => { if (rootRow) controller.startCreate(rootRow, 'folder') }}
        >
          <FolderPlus size={15} strokeWidth={2} />
        </button>
        <button
          type="button" className={styles.iconBtn} title="Collapse all folders" aria-label="Collapse all folders"
          onClick={controller.collapseAll}
        >
          <ListTree size={15} strokeWidth={2} />
        </button>
      </div>

      <div className={styles.tree}>
        {showPinned && (
          <>
            <div className={styles.pinnedLabel}>Pinned</div>
            {controller.pinnedRows.map((row) => renderRow(row, controller))}
          </>
        )}
        {showPinned && showMain && <div className={styles.pinnedDivider} />}
        {showMain && controller.rows.map((row) => renderRow(row, controller))}
      </div>

      <ContextMenu controller={controller} />
      <DeleteDialog controller={controller} />
      <Toast message={controller.toast} />
    </div>
  )
}
