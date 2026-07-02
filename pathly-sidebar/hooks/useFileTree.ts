import { useCallback, useMemo, useRef, useState } from 'react'
import type {
  DeleteTarget,
  FileTreeController,
  FlatRow,
  ItemKind,
  MenuState,
  NodeType,
  PlanState,
  TreeNode,
} from '../types'
import { EXT, kindOf } from '../lib/kinds'
import {
  addNode,
  canDropInto,
  findNode,
  moveNode as moveNodeUtil,
  removeNode,
  renameNode,
  sortNodes,
} from '../lib/treeUtils'
import { SAMPLE_COLLAPSED, SAMPLE_TREE } from '../lib/sampleTree'

/** MIME used by Pathly for internal reorg drags. */
export const PATHLY_DRAG_MIME = 'application/x-pathly-reorg'

const CREATE_PLACEHOLDER: Record<string, string> = {
  file: 'filename',
  folder: 'folder',
  flow: 'name.flow.yaml',
  skill: 'name.skill.md',
  agent: 'name.agent.md',
  plan: 'plan-name',
}

export interface UseFileTreeOptions {
  initialTree?: TreeNode[]
  initialCollapsed?: Record<string, boolean>
  initialActivePath?: string | null
  projectName?: string
  /** Called on single-click of a file (selection only — never opens an editor). */
  onSelectFile?: (path: string) => void
}

interface CreateState {
  parent: string
  type: NodeType
}

/**
 * Owns all workspace-tree state and mutations. Returns a {@link FileTreeController}
 * plus the project name; feed it straight into <Sidebar controller={…} />.
 */
export function useFileTree(opts: UseFileTreeOptions = {}): {
  controller: FileTreeController
  projectName: string
} {
  const projectName = opts.projectName ?? 'acme-api'

  const [tree, setTree] = useState<TreeNode[]>(opts.initialTree ?? SAMPLE_TREE)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(
    opts.initialCollapsed ?? SAMPLE_COLLAPSED,
  )
  const [activePath, setActivePath] = useState<string | null>(
    opts.initialActivePath ?? 'src/index.ts',
  )
  const [filter, setFilterState] = useState('')
  const [menu, setMenu] = useState<MenuState | null>(null)
  const [editingPath, setEditingPath] = useState<string | null>(null)
  const [editValue, setEditValueState] = useState('')
  const [creating, setCreating] = useState<CreateState | null>(null)
  const [createValue, setCreateValueState] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [dragPath, setDragPath] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)

  const toastTimer = useRef<ReturnType<typeof setTimeout>>()

  const isOpen = useCallback(
    (path: string) => (filter.trim() ? true : collapsed[path] !== false),
    [filter, collapsed],
  )

  // ── selection / expand ────────────────────────────────────────────────
  const select = useCallback(
    (path: string) => {
      setActivePath(path)
      opts.onSelectFile?.(path)
    },
    [opts],
  )

  const toggle = useCallback((path: string) => {
    setCollapsed((c) => ({ ...c, [path]: c[path] === false ? true : false }))
  }, [])

  const collapseAll = useCallback(() => {
    const acc: Record<string, boolean> = {}
    const walk = (nodes: TreeNode[], parent: string) => {
      for (const n of nodes) {
        const p = parent ? `${parent}/${n.name}` : n.name
        if (n.type === 'folder') {
          acc[p] = false
          if (n.children) walk(n.children, p)
        }
      }
    }
    walk(tree, '')
    setCollapsed(acc)
    setMenu(null)
  }, [tree])

  // ── context menu ──────────────────────────────────────────────────────
  const openMenu = useCallback(
    (e: MouseEvent | React.MouseEvent, path: string, node: TreeNode, isRoot: boolean) => {
      e.preventDefault()
      e.stopPropagation()
      const kind: ItemKind = isRoot ? 'folder' : kindOf(path, node)
      setMenu({
        x: (e as MouseEvent).clientX,
        y: (e as MouseEvent).clientY,
        path,
        name: node.name,
        kind,
        isRoot,
        state: node.state ?? null,
      })
      setCreating(null)
      setEditingPath(null)
    },
    [],
  )
  const closeMenu = useCallback(() => setMenu(null), [])

  // ── create ────────────────────────────────────────────────────────────
  const startCreate = useCallback((parent: string, type: NodeType) => {
    setCreating({ parent, type })
    setCreateValueState('')
    setMenu(null)
    setCollapsed((c) => ({ ...c, [parent]: true }))
  }, [])

  const submitCreate = useCallback(() => {
    setCreating((c) => {
      if (!c) return null
      let name = createValue.trim()
      if (!name) return null
      let node: TreeNode
      if (c.type === 'folder') node = { name, type: 'folder', children: [] }
      else {
        node = { name, type: 'file' }
      }
      setTree((t) => addNode(t, c.parent ? c.parent.split('/') : [], node))
      return null
    })
    setCreateValueState('')
  }, [createValue])

  const cancelCreate = useCallback(() => {
    setCreating(null)
    setCreateValueState('')
  }, [])

  // ── rename ────────────────────────────────────────────────────────────
  const startRename = useCallback((path: string, name: string) => {
    setEditingPath(path)
    setEditValueState(name)
    setMenu(null)
  }, [])

  const submitRename = useCallback(() => {
    setEditingPath((p) => {
      if (p == null) return null
      const name = editValue.trim()
      const segs = p.split('/')
      if (name && name !== segs[segs.length - 1]) {
        setTree((t) => renameNode(t, segs, name))
      }
      return null
    })
  }, [editValue])

  const cancelRename = useCallback(() => setEditingPath(null), [])

  // ── delete ────────────────────────────────────────────────────────────
  const askDelete = useCallback((path: string, name: string, kind: ItemKind) => {
    setDeleteTarget({ path, name, kind })
    setMenu(null)
  }, [])

  const confirmDelete = useCallback(() => {
    setDeleteTarget((t) => {
      if (!t) return null
      setTree((tr) => removeNode(tr, t.path.split('/')))
      setActivePath((a) => (a === t.path ? null : a))
      return null
    })
  }, [])

  const cancelDelete = useCallback(() => setDeleteTarget(null), [])

  // ── copy path ─────────────────────────────────────────────────────────
  const flash = useCallback((msg: string) => {
    setToast(msg)
    setMenu(null)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 1800)
  }, [])

  const copyPath = useCallback(
    (path: string, isRoot: boolean) => {
      const abs = isRoot ? projectName : `${projectName}/${path}`
      void navigator.clipboard?.writeText(abs).catch(() => {})
      flash(`Copied  ${abs}`)
    },
    [projectName, flash],
  )
  const copyRelPath = useCallback(
    (path: string, isRoot: boolean) => {
      const rel = isRoot ? '.' : path
      void navigator.clipboard?.writeText(rel).catch(() => {})
      flash(`Copied  ${rel}`)
    },
    [flash],
  )

  // ── drag & drop ───────────────────────────────────────────────────────
  const onDragStart = useCallback((e: React.DragEvent, path: string) => {
    e.stopPropagation()
    e.dataTransfer.effectAllowed = 'move'
    try {
      e.dataTransfer.setData(PATHLY_DRAG_MIME, path)
      e.dataTransfer.setData('text/plain', path)
    } catch {
      /* noop */
    }
    setDragPath(path)
    setMenu(null)
  }, [])

  const onDragOver = useCallback(
    (e: React.DragEvent, destFolder: string) => {
      if (!canDropInto(dragPath, destFolder)) return
      e.preventDefault()
      e.stopPropagation()
      e.dataTransfer.dropEffect = 'move'
      setDropTarget((d) => (d !== destFolder ? destFolder : d))
    },
    [dragPath],
  )

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.stopPropagation()
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent, destFolder: string) => {
      e.preventDefault()
      e.stopPropagation()
      const src = dragPath
      setDragPath(null)
      setDropTarget(null)
      if (!src) return
      setTree((t) => {
        const res = moveNodeUtil(t, src, destFolder)
        if (!res) return t
        setCollapsed((c) => ({ ...c, [destFolder]: true }))
        setActivePath((a) => (a === src ? res.newPath : a))
        return res.tree
      })
    },
    [dragPath],
  )

  const onDragEnd = useCallback(() => {
    setDragPath(null)
    setDropTarget(null)
  }, [])

  // ── flatten to rows ───────────────────────────────────────────────────
  const rows = useMemo<FlatRow[]>(() => {
    const out: FlatRow[] = []

    const createRow = (parent: string, level: number): FlatRow => ({
      key: `__create__:${parent}`,
      path: parent,
      parent,
      name: '',
      node: { name: '', type: creating?.type ?? 'file' },
      kind: creating?.type === 'folder' ? 'folder' : 'file',
      level,
      isRoot: false,
      isFolder: creating?.type === 'folder',
      open: false,
      isActive: false,
      editing: false,
      isDragging: false,
      isDropTarget: false,
      isCreate: true,
      createType: creating?.type ?? 'file',
    })

    const push = (node: TreeNode, level: number, parent: string) => {
      const path = parent ? `${parent}/${node.name}` : node.name
      const isFolder = node.type === 'folder'
      const kind = kindOf(path, node)
      const open = isFolder && isOpen(path)
      out.push({
        key: path,
        path,
        parent,
        name: node.name,
        node,
        kind,
        level,
        isRoot: false,
        isFolder,
        open,
        isActive: activePath === path,
        editing: editingPath === path,
        isDragging: dragPath === path,
        isDropTarget: isFolder && dropTarget === path,
      })
      if (isFolder && open && creating && creating.parent === path) out.push(createRow(path, level + 1))
      if (isFolder && open && node.children) {
        for (const child of sortNodes(node.children)) push(child, level + 1, path)
      }
    }

    // workspace root
    out.push({
      key: '__root__',
      path: '',
      parent: '',
      name: projectName,
      node: { name: projectName, type: 'folder' },
      kind: 'folder',
      level: 0,
      isRoot: true,
      isFolder: true,
      open: true,
      isActive: false,
      editing: editingPath === '',
      isDragging: false,
      isDropTarget: dropTarget === '',
    })
    if (creating && creating.parent === '') out.push(createRow('', 1))
    for (const n of sortNodes(tree)) push(n, 1, '')

    // filter
    const q = filter.trim().toLowerCase()
    if (!q) return out
    const kept = new Set<string>(['__root__'])
    for (const r of out) {
      if (!r.isCreate && r.key !== '__root__' && r.key.toLowerCase().includes(q)) kept.add(r.key)
    }
    for (const r of out) {
      if (kept.has(r.key) && r.key !== '__root__') {
        const segs = r.key.split('/')
        for (let i = 1; i < segs.length; i++) kept.add(segs.slice(0, i).join('/'))
      }
    }
    for (const r of out) {
      if (r.isFolder && r.key !== '__root__') {
        for (const k of kept) {
          if (k.startsWith(`${r.key}/`)) {
            kept.add(r.key)
            break
          }
        }
      }
    }
    return out.filter((r) => r.isCreate || kept.has(r.key))
  }, [tree, collapsed, activePath, editingPath, creating, filter, dragPath, dropTarget, isOpen, projectName])

  const createPlaceholder = creating ? CREATE_PLACEHOLDER[creating.type] ?? 'name' : ''

  const controller: FileTreeController = {
    rows,
    filter,
    menu,
    deleteTarget,
    toast,
    editValue,
    createValue,
    createPlaceholder,
    setFilter: setFilterState,
    select,
    toggle,
    openMenu,
    closeMenu,
    startCreate,
    setCreateValue: setCreateValueState,
    submitCreate,
    cancelCreate,
    startRename,
    setEditValue: setEditValueState,
    submitRename,
    cancelRename,
    askDelete,
    confirmDelete,
    cancelDelete,
    collapseAll,
    copyPath,
    copyRelPath,
    onDragStart,
    onDragOver,
    onDragLeave,
    onDrop,
    onDragEnd,
  }

  return { controller, projectName }
}
