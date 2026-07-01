// Shared types for the Workspace tree — a plain, real project file tree
// (folders + files) rooted at the open project, like a code-editor explorer.
//
// Every row is keyed by its real absolute filesystem path (`fsPath`) so that
// selection, rename, delete and move operate on real files. There is exactly
// one root (the project), so a child's path is just parent + '/' + name — no
// lifecycle states and no flow/skill/agent kinds (those live in the Library).

import type { DragEvent, MouseEvent } from 'react'

export type WsKind = 'root' | 'folder' | 'file'

/** Cached directory listing (children names), loaded lazily on expand. */
export interface WsListing {
  dirs: string[]
  files: string[]
  loaded: boolean
}

/** One flattened, rendered row. */
export interface WsRow {
  /** Stable unique id (the real fsPath, or `__create__:<parent>` for inputs). */
  key: string
  /** Absolute path for filesystem ops. */
  fsPath: string
  /** Containing directory — the drop target when this row is a file. */
  parentFsPath: string
  name: string
  kind: WsKind
  level: number
  /** The project root row (never renamed/deleted/dragged). */
  isRoot: boolean
  /** Folder-like row — toggles instead of selecting. */
  isFolder: boolean
  /** A feature folder (direct child of pathly/features) — offers "Open board". */
  isFeature: boolean
  open: boolean
  /** The currently-selected file. */
  isActive: boolean
  isDirty: boolean
  editing: boolean
  /** Inline "new file/folder" input row. */
  isCreate?: boolean
  createType?: 'file' | 'folder'
}

export interface WsMenu {
  x: number
  y: number
  row: WsRow
}

/**
 * Controller returned by `useWorkspaceTree`. TreeRow and the panel drive every
 * interaction through this object so the presentational components stay reusable.
 */
export interface WorkspaceTreeController {
  rows: WsRow[]
  /** The pinned pathly/ subtree, rendered above the project root. Empty if none. */
  pinnedRows: WsRow[]
  filter: string
  /** Which tree the search box filters: the whole project, or only pathly/. */
  searchScope: 'project' | 'pathly'
  /** How search results render: filtered tree (in place) or a flat results list. */
  searchView: 'tree' | 'list'
  editValue: string
  createValue: string
  createPlaceholder: string
  menu: WsMenu | null
  deleteTarget: WsRow | null
  toast: string | null

  setFilter(v: string): void
  setSearchScope(scope: 'project' | 'pathly'): void
  setSearchView(view: 'tree' | 'list'): void
  /** Highlight a file (no open), or toggle a folder. Single-click never opens. */
  select(row: WsRow): void
  /** Open a file in the matching editor panel — explicit menu/right-click action. */
  open(row: WsRow): void
  /** Open a feature folder's board in the Command Center — explicit menu action. */
  openBoard(row: WsRow): void
  toggle(row: WsRow): void
  collapseAll(): void

  openMenu(e: MouseEvent, row: WsRow): void
  closeMenu(): void

  startCreate(row: WsRow, type: 'file' | 'folder'): void
  setCreateValue(v: string): void
  submitCreate(): void
  cancelCreate(): void

  startRename(row: WsRow): void
  setEditValue(v: string): void
  submitRename(): void
  cancelRename(): void

  askDelete(row: WsRow): void
  confirmDelete(): void
  cancelDelete(): void

  copyPath(row: WsRow): void

  onDragStart(e: DragEvent, row: WsRow): void
  onDragOver(e: DragEvent, destFolder: string): void
  onDragLeave(e: DragEvent): void
  onDrop(e: DragEvent, destFolder: string): void
  onDragEnd(): void
}
