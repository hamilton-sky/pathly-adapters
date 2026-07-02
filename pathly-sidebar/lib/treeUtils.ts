import type { TreeNode } from '../types'

/** Folders first, then files; each group sorted naturally by name. */
export function sortNodes(nodes: TreeNode[]): TreeNode[] {
  return [...nodes].sort((a, b) =>
    a.type === b.type
      ? a.name.localeCompare(b.name, undefined, { numeric: true })
      : a.type === 'folder'
        ? -1
        : 1,
  )
}

/** Insert `node` into the folder addressed by `segs` (empty = root). */
export function addNode(nodes: TreeNode[], segs: string[], node: TreeNode): TreeNode[] {
  if (segs.length === 0) return sortNodes([...nodes, node])
  return nodes.map((n) =>
    n.name === segs[0]
      ? { ...n, children: addNode(n.children ?? [], segs.slice(1), node) }
      : n,
  )
}

/** Rename the node addressed by `segs`. */
export function renameNode(nodes: TreeNode[], segs: string[], name: string): TreeNode[] {
  return nodes.map((n) => {
    if (n.name !== segs[0]) return n
    if (segs.length === 1) return { ...n, name }
    return { ...n, children: renameNode(n.children ?? [], segs.slice(1), name) }
  })
}

/** Remove the node addressed by `segs`. */
export function removeNode(nodes: TreeNode[], segs: string[]): TreeNode[] {
  if (segs.length === 1) return nodes.filter((n) => n.name !== segs[0])
  return nodes.map((n) =>
    n.name === segs[0]
      ? { ...n, children: removeNode(n.children ?? [], segs.slice(1)) }
      : n,
  )
}

/** Resolve the node at `segs`, or null. */
export function findNode(nodes: TreeNode[], segs: string[]): TreeNode | null {
  let level: TreeNode[] | undefined = nodes
  let node: TreeNode | null = null
  for (const s of segs) {
    node = (level ?? []).find((n) => n.name === s) ?? null
    if (!node) return null
    level = node.children
  }
  return node
}

/**
 * Is it valid to drop `srcPath` into `destFolder`?
 * Blocks: onto itself, into its own descendant, or into its current parent.
 */
export function canDropInto(srcPath: string | null, destFolder: string | null): boolean {
  if (srcPath == null || destFolder == null) return false
  if (srcPath === destFolder) return false
  if ((destFolder + '/').startsWith(srcPath + '/')) return false
  const srcParent = srcPath.includes('/') ? srcPath.slice(0, srcPath.lastIndexOf('/')) : ''
  if (srcParent === destFolder) return false
  return true
}

/** Move `srcPath` into `destFolder`, returning the new tree + new path. */
export function moveNode(
  tree: TreeNode[],
  srcPath: string,
  destFolder: string,
): { tree: TreeNode[]; newPath: string } | null {
  if (!canDropInto(srcPath, destFolder)) return null
  const srcSegs = srcPath.split('/')
  const node = findNode(tree, srcSegs)
  if (!node) return null
  let next = removeNode(tree, srcSegs)
  next = addNode(next, destFolder ? destFolder.split('/') : [], node)
  return { tree: next, newPath: destFolder ? `${destFolder}/${node.name}` : node.name }
}
