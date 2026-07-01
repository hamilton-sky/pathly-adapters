import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent, MouseEvent } from 'react'
import { useStore } from '../../../store'
import { useCommandCenterStore } from '../../../store/commandCenterStore'
import type { WsListing, WsMenu, WsRow, WorkspaceTreeController } from './types'
import { buildRows, IGNORE } from './buildRows'
import { createEntry, deleteEntry, loadListing, moveEntry, renameEntry } from './treeOps'

const DRAG_MIME = 'application/x-pathly-ws-move'
const PIN = 'pin:'

function basename(p: string): string {
  return p.split(/[\\/]/).filter(Boolean).pop() ?? p
}

interface EditState { key: string; fsPath: string; parentFsPath: string; isFolder: boolean }
interface CreateState { parentFsPath: string; parentKey: string; type: 'file' | 'folder' }

/** Owns all workspace-tree state and mutations; feed the result to <WorkspaceTree>. */
export function useWorkspaceTree(): { controller: WorkspaceTreeController } {
  const {
    projectPath, selectedItem, setSelectedItem, setActivePanel, setActiveTopic,
    setMdEditorPath, setLastUsedFlowPath, dirtyItems,
  } = useStore()
  const setMainFeature = useCommandCenterStore((s) => s.setMainFeature)

  const [listing, setListing] = useState<Record<string, WsListing>>({})
  const [openKeys, setOpenKeys] = useState<Set<string>>(() => new Set())
  const [filter, setFilter] = useState('')
  const [editing, setEditing] = useState<EditState | null>(null)
  const [editValue, setEditValue] = useState('')
  const [creating, setCreating] = useState<CreateState | null>(null)
  const [createValue, setCreateValue] = useState('')
  const [menu, setMenu] = useState<WsMenu | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<WsRow | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [allLoaded, setAllLoaded] = useState(false)
  const [searchScope, setSearchScope] = useState<'project' | 'pathly'>('project')
  const [searchView, setSearchView] = useState<'tree' | 'list'>('tree')

  const toastTimer = useRef<ReturnType<typeof setTimeout>>()

  const rootPath = projectPath
  const rootName = basename(projectPath || 'workspace')
  const pathlyDir = projectPath ? `${projectPath}/pathly` : ''
  const featuresDir = projectPath ? `${projectPath}/pathly/features` : ''

  const refresh = useCallback(async (dir: string): Promise<void> => {
    const l = await loadListing(dir)
    setListing((prev) => ({ ...prev, [dir]: l }))
  }, [])

  const ensureListed = useCallback((dir: string): void => {
    setListing((prev) => { if (!prev[dir]?.loaded) void refresh(dir); return prev })
  }, [refresh])

  // Initial load + open both roots (project + pinned pathly); reload on project switch.
  useEffect(() => {
    setAllLoaded(false)
    if (!projectPath) { setListing({}); setOpenKeys(new Set()); return }
    setOpenKeys(new Set([projectPath, `${PIN}${projectPath}/pathly`]))
    void refresh(projectPath)
    void refresh(`${projectPath}/pathly`)
  }, [projectPath, refresh])

  // Filesystem watcher → re-list every currently-loaded directory.
  useEffect(() => {
    if (!projectPath) return
    const watchApi = window.pathly?.watch
    if (watchApi?.watchWorkspace) void watchApi.watchWorkspace(projectPath)
    if (!watchApi?.onWorkspaceChanged) return
    return watchApi.onWorkspaceChanged(() => {
      setListing((prev) => { for (const dir of Object.keys(prev)) void refresh(dir); return prev })
    })
  }, [projectPath, refresh])

  // First non-empty search loads the whole project tree once (bounded, noise
  // skipped) so the filter matches every file — not just expanded folders.
  useEffect(() => {
    if (!filter.trim() || allLoaded || !projectPath) return
    let cancelled = false
    void (async () => {
      const acc: Record<string, WsListing> = {}
      const queue: string[] = [projectPath]
      let count = 0
      while (queue.length > 0 && count < 6000) {
        const dir = queue.shift() as string
        if (acc[dir]) continue
        const l = await loadListing(dir)
        if (cancelled) return
        acc[dir] = l
        count += 1
        for (const d of l.dirs) if (!IGNORE.has(d)) queue.push(`${dir}/${d}`)
      }
      if (!cancelled) { setListing((prev) => ({ ...acc, ...prev })); setAllLoaded(true) }
    })()
    return () => { cancelled = true }
  }, [filter, allLoaded, projectPath])

  const toggle = useCallback((row: WsRow): void => {
    if (!row.isFolder) return
    setOpenKeys((prev) => {
      const next = new Set(prev)
      if (next.has(row.key)) next.delete(row.key)
      else { next.add(row.key); ensureListed(row.fsPath) }
      return next
    })
  }, [ensureListed])

  // Single-click: highlight a file (never opens) or toggle a folder.
  const select = useCallback((row: WsRow): void => {
    if (row.isFolder) { toggle(row); return }
    setSelectedItem({ name: row.name, path: row.fsPath, type: row.name.endsWith('.flow.yaml') ? 'flow' : 'plan' })
  }, [toggle, setSelectedItem])

  // Explicit "Open" menu action: route a file to the matching editor panel.
  const open = useCallback((row: WsRow): void => {
    if (row.isFolder) { toggle(row); return }
    const p = row.fsPath
    setSelectedItem({ name: row.name, path: p, type: row.name.endsWith('.flow.yaml') ? 'flow' : 'plan' })
    if (row.name.endsWith('.flow.yaml')) { setLastUsedFlowPath(p); setActivePanel('flow') }
    else if (row.name.endsWith('.md')) { setMdEditorPath(p); setActivePanel('markdown-editor') }
    else setActivePanel('editor')
    setMenu(null)
  }, [toggle, setSelectedItem, setLastUsedFlowPath, setActivePanel, setMdEditorPath])

  // Explicit "Open board" menu action on a feature folder → Command Center.
  const openBoard = useCallback((row: WsRow): void => {
    if (!row.isFeature) return
    setMainFeature(row.name)
    setActiveTopic(row.name)
    setActivePanel('command-center')
    setMenu(null)
  }, [setMainFeature, setActiveTopic, setActivePanel])

  const collapseAll = useCallback((): void => {
    setOpenKeys(new Set())
  }, [])

  const flash = useCallback((msg: string): void => {
    setToast(msg); setMenu(null)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 1800)
  }, [])

  const openMenu = useCallback((e: MouseEvent, row: WsRow): void => {
    e.preventDefault(); e.stopPropagation()
    setMenu({ x: e.clientX, y: e.clientY, row }); setCreating(null); setEditing(null)
  }, [])
  const closeMenu = useCallback((): void => setMenu(null), [])

  const startCreate = useCallback((row: WsRow, type: 'file' | 'folder'): void => {
    setCreating({ parentFsPath: row.fsPath, parentKey: row.key, type }); setCreateValue(''); setMenu(null)
    setOpenKeys((prev) => new Set(prev).add(row.key)); ensureListed(row.fsPath)
  }, [ensureListed])
  const submitCreate = useCallback((): void => {
    const c = creating; const name = createValue.trim()
    setCreating(null); setCreateValue('')
    if (!c || !name) return
    void createEntry(c.parentFsPath, name, c.type).then(() => refresh(c.parentFsPath))
  }, [creating, createValue, refresh])
  const cancelCreate = useCallback((): void => { setCreating(null); setCreateValue('') }, [])

  const startRename = useCallback((row: WsRow): void => {
    setEditing({ key: row.key, fsPath: row.fsPath, parentFsPath: row.parentFsPath, isFolder: row.isFolder })
    setEditValue(row.name); setMenu(null)
  }, [])
  const submitRename = useCallback((): void => {
    const e = editing; const name = editValue.trim()
    setEditing(null)
    if (!e || !name || name === basename(e.fsPath)) return
    void renameEntry(e.fsPath, e.parentFsPath, name, e.isFolder).then(() => refresh(e.parentFsPath))
  }, [editing, editValue, refresh])
  const cancelRename = useCallback((): void => setEditing(null), [])

  const askDelete = useCallback((row: WsRow): void => { setDeleteTarget(row); setMenu(null) }, [])
  const confirmDelete = useCallback((): void => {
    const t = deleteTarget; setDeleteTarget(null)
    if (!t) return
    void deleteEntry(t.fsPath, t.isFolder).then(() => refresh(t.parentFsPath))
    if (selectedItem?.path === t.fsPath) setSelectedItem(null)
  }, [deleteTarget, refresh, selectedItem, setSelectedItem])
  const cancelDelete = useCallback((): void => setDeleteTarget(null), [])

  const copyPath = useCallback((row: WsRow): void => {
    void navigator.clipboard?.writeText(row.fsPath).catch(() => {})
    flash(`Copied ${row.fsPath}`)
  }, [flash])

  const onDragStart = useCallback((e: DragEvent, row: WsRow): void => {
    if (row.isRoot) return
    e.stopPropagation(); e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData(DRAG_MIME, JSON.stringify({ src: row.fsPath, isFolder: row.isFolder })) } catch { /* noop */ }
    setMenu(null)
  }, [])
  const onDragOver = useCallback((e: DragEvent): void => {
    if (!e.dataTransfer.types.includes(DRAG_MIME)) return
    e.preventDefault(); e.dataTransfer.dropEffect = 'move'
  }, [])
  const onDragLeave = useCallback((): void => {}, [])
  const onDrop = useCallback((e: DragEvent, destFolder: string): void => {
    e.preventDefault(); e.stopPropagation()
    const raw = e.dataTransfer.getData(DRAG_MIME)
    if (!raw) return
    let payload: { src: string; isFolder: boolean }
    try { payload = JSON.parse(raw) } catch { return }
    const srcParent = payload.src.slice(0, payload.src.lastIndexOf('/'))
    if (srcParent === destFolder) return
    void moveEntry(payload.src, destFolder, payload.isFolder).then((np) => {
      if (!np) return
      void refresh(srcParent); void refresh(destFolder)
      setOpenKeys((prev) => new Set(prev).add(destFolder))
      if (selectedItem && selectedItem.path === payload.src) setSelectedItem({ ...selectedItem, path: np })
    })
  }, [refresh, selectedItem, setSelectedItem])
  const onDragEnd = useCallback((): void => {}, [])

  const base = {
    featuresDir, listing, openKeys,
    selectedPath: selectedItem?.path ?? null, dirtyItems,
    editingKey: editing?.key ?? null, creating,
  }

  const rows = useMemo(
    () => buildRows({ ...base, keyPrefix: '', rootPath, rootName, filter: searchScope === 'project' ? filter : '' }),
    [base, rootPath, rootName, filter, searchScope],
  )

  const pathlyListing = pathlyDir ? listing[pathlyDir] : undefined
  const hasPathly = !!pathlyListing?.loaded && pathlyListing.dirs.length + pathlyListing.files.length > 0
  const pinnedRows = useMemo(
    () => (hasPathly
      ? buildRows({ ...base, keyPrefix: PIN, rootPath: pathlyDir, rootName: 'pathly', filter: searchScope === 'pathly' ? filter : '' })
      : []),
    [base, hasPathly, pathlyDir, filter, searchScope],
  )

  const createPlaceholder = creating?.type === 'folder' ? 'folder-name' : 'filename.ext'

  const controller: WorkspaceTreeController = {
    rows, pinnedRows, filter, searchScope, searchView, editValue, createValue, createPlaceholder, menu, deleteTarget, toast,
    setFilter, setSearchScope, setSearchView, select, open, openBoard, toggle, collapseAll,
    openMenu, closeMenu,
    startCreate, setCreateValue, submitCreate, cancelCreate,
    startRename, setEditValue, submitRename, cancelRename,
    askDelete, confirmDelete, cancelDelete,
    copyPath,
    onDragStart, onDragOver, onDragLeave, onDrop, onDragEnd,
  }
  return { controller }
}
