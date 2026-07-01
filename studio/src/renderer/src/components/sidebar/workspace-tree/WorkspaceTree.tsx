import { FilePlus, FolderPlus, FolderTree, List, ListTree, Search } from 'lucide-react'
import { useWorkspaceTree } from './useWorkspaceTree'
import { TreeRow } from './TreeRow/TreeRow'
import { CreateRow } from './CreateRow/CreateRow'
import { ResultRow } from './ResultRow/ResultRow'
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
  const rootPath = rootRow?.fsPath ?? ''
  const scope = controller.searchScope
  const view = controller.searchView
  const q = controller.filter.trim().toLowerCase()
  const searching = q.length > 0

  // During search, only the scoped tree is active; the other is hidden.
  const activeRows = scope === 'pathly' ? controller.pinnedRows : controller.rows
  const matches = searching
    ? activeRows.filter((r) => !r.isCreate && !r.isRoot && r.name.toLowerCase().includes(q))
    : []

  const relDir = (r: WsRow): string => {
    const p = r.parentFsPath
    if (!rootPath || p === rootPath) return ''
    return p.startsWith(`${rootPath}/`) ? p.slice(rootPath.length + 1) : p
  }

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
        {searching ? (
          <>
            <div className={styles.resultsHeader}>
              <span className={styles.resultsCount}>
                {matches.length} {matches.length === 1 ? 'result' : 'results'}
              </span>
              <div className={styles.viewToggle} role="group" aria-label="Search results view">
                <button
                  type="button" className={styles.viewBtn} title="Tree view" aria-label="Tree view"
                  {...(view === 'tree' ? { 'data-active': 'true' } : {})}
                  onClick={() => controller.setSearchView('tree')}
                >
                  <FolderTree size={14} strokeWidth={2} />
                </button>
                <button
                  type="button" className={styles.viewBtn} title="List view" aria-label="List view"
                  {...(view === 'list' ? { 'data-active': 'true' } : {})}
                  onClick={() => controller.setSearchView('list')}
                >
                  <List size={14} strokeWidth={2} />
                </button>
              </div>
            </div>
            {view === 'list'
              ? matches.map((row) => <ResultRow key={row.key} row={row} relDir={relDir(row)} controller={controller} />)
              : activeRows.map((row) => renderRow(row, controller))}
          </>
        ) : (
          <>
            {controller.pinnedRows.length > 0 && (
              <>
                <div className={styles.pinnedLabel}>Pinned</div>
                {controller.pinnedRows.map((row) => renderRow(row, controller))}
                <div className={styles.pinnedDivider} />
              </>
            )}
            {controller.rows.map((row) => renderRow(row, controller))}
          </>
        )}
      </div>

      <ContextMenu controller={controller} />
      <DeleteDialog controller={controller} />
      <Toast message={controller.toast} />
    </div>
  )
}
