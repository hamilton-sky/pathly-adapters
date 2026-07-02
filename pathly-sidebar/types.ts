// Shared types for the Pathly workspace sidebar.

export type NodeType = 'file' | 'folder'

export type PlanState =
  | 'PLANNING'
  | 'BUILDING'
  | 'REVIEWING'
  | 'TESTING'
  | 'RETRO'
  | 'DONE'

export interface TreeNode {
  name: string
  type: NodeType
  /** Present on plan folders (pathly/plans/<name>). Drives the state pill. */
  state?: PlanState
  children?: TreeNode[]
}

/** Visual/behavioural classification derived from a node + its path. */
export type ItemKind = 'flow' | 'skill' | 'agent' | 'plan' | 'folder' | 'file'

/** A single rendered row (flattened from the tree). */
export interface FlatRow {
  key: string
  /** '' for the workspace root. */
  path: string
  parent: string
  name: string
  node: TreeNode
  kind: ItemKind
  level: number
  isRoot: boolean
  isFolder: boolean
  open: boolean
  isActive: boolean
  editing: boolean
  isDragging: boolean
  isDropTarget: boolean
  /** Inline "new file/folder" input row. */
  isCreate?: boolean
  createType?: NodeType
}

export interface MenuState {
  x: number
  y: number
  path: string
  name: string
  kind: ItemKind
  isRoot: boolean
  state: PlanState | null
}

export interface DeleteTarget {
  path: string
  name: string
  kind: ItemKind
}

/**
 * The controller returned by `useFileTree`. Sidebar and its children drive
 * every interaction through this object, so the presentational components
 * (TreeRow, ContextMenu, …) stay reusable.
 */
export interface FileTreeController {
  rows: FlatRow[]
  filter: string
  menu: MenuState | null
  deleteTarget: DeleteTarget | null
  toast: string | null
  editValue: string
  createValue: string
  createPlaceholder: string

  setFilter(v: string): void
  select(path: string): void
  toggle(path: string): void

  openMenu(e: MouseEvent | React.MouseEvent, path: string, node: TreeNode, isRoot: boolean): void
  closeMenu(): void

  startCreate(parent: string, type: NodeType): void
  setCreateValue(v: string): void
  submitCreate(): void
  cancelCreate(): void

  startRename(path: string, name: string): void
  setEditValue(v: string): void
  submitRename(): void
  cancelRename(): void

  askDelete(path: string, name: string, kind: ItemKind): void
  confirmDelete(): void
  cancelDelete(): void

  collapseAll(): void
  copyPath(path: string, isRoot: boolean): void
  copyRelPath(path: string, isRoot: boolean): void

  // drag & drop
  onDragStart(e: React.DragEvent, path: string): void
  onDragOver(e: React.DragEvent, destFolder: string): void
  onDragLeave(e: React.DragEvent): void
  onDrop(e: React.DragEvent, destFolder: string): void
  onDragEnd(): void
}
