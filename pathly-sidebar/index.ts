// Pathly workspace sidebar — public API.
//
//   import { Sidebar, useFileTree } from '@/components/pathly-sidebar'
//
//   function WorkspacePane() {
//     const { controller } = useFileTree()
//     return <Sidebar controller={controller} />
//   }

export { Sidebar } from './Sidebar/Sidebar'
export { useFileTree, PATHLY_DRAG_MIME } from './hooks/useFileTree'
export type { UseFileTreeOptions } from './hooks/useFileTree'

// Sub-components (exported so they can be reused / restyled individually)
export { TreeRow } from './TreeRow/TreeRow'
export { CreateRow } from './CreateRow/CreateRow'
export { ContextMenu } from './ContextMenu/ContextMenu'
export { DeleteDialog } from './DeleteDialog/DeleteDialog'
export { Toast } from './Toast/Toast'
export { FileIcon } from './FileIcon/FileIcon'
export { FolderIcon } from './FolderIcon/FolderIcon'
export { StatePill } from './StatePill/StatePill'

// Lib
export * from './lib/kinds'
export * from './lib/treeUtils'
export { SAMPLE_TREE, SAMPLE_COLLAPSED } from './lib/sampleTree'

export type {
  TreeNode,
  NodeType,
  PlanState,
  ItemKind,
  FlatRow,
  MenuState,
  DeleteTarget,
  FileTreeController,
} from './types'
