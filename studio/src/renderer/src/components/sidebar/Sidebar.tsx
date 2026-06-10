import { useEffect, useDeferredValue, useRef, useState } from 'react'
import React from 'react'
import { useStore } from '../../store'
import { useUiStore } from '../../store/uiStore'
import type { PathlyItem, PathlyCanvasDragItem, PathlyReorgDragItem } from '../../types'
import { PATHLY_DRAG_MIME } from '../../types'
import { listDir, listDirs } from '../../services/pathlyApi'
import { useProjectFiles } from '../../hooks/useProjectFiles'
import { usePlanFiles } from '../../hooks/usePlanFiles'
import { WorkspacePanel } from './panels/WorkspacePanel'
import LibraryCatalog from '../shared/LibraryCatalog/LibraryCatalog'
import SkillSplitModal from '../shared/SkillSplitModal/SkillSplitModal'
import type { CatalogGroup, CatalogItemData } from '../shared/LibraryCatalog/useCatalogData'
import { useSkillNotebookStore } from '../../store/skillNotebookStore'
import { useSidebarResize } from './shell/useSidebarResize'
import { useWindowWidth } from './shell/useWindowWidth'
import { TabBar } from './shell/TabBar'
import { FilterRow } from './shell/FilterRow'
import { BottomNav } from './shell/BottomNav'
import { BrightskyProfile } from './shell/BrightskyProfile'
import { SidebarDialogs } from './shell/SidebarDialogs'
import { IconStrip } from './shell/IconStrip'
import type { Section } from './types'
import styles from './Sidebar.module.css'

const POPOVER_BREAKPOINT = 700

const CORE_RESOURCE_DIRS = [
  'src/pathly_data/core/flows',
  'src/pathly_data/core/skills',
  'src/pathly_data/core/agents',
  'src/pathly_data/core/templates',
]

async function hasCoreEntries(root: string, relDir: string): Promise<boolean> {
  const dir = `${root}/${relDir}`
  const [files, dirs] = await Promise.all([
    listDir(dir).catch(() => [] as string[]),
    listDirs(dir).catch(() => [] as string[]),
  ])
  return files.length > 0 || dirs.length > 0
}

async function isPathlyCoreRoot(root: string): Promise<boolean> {
  if (!root) return false
  const checks = await Promise.all(CORE_RESOURCE_DIRS.map((dir) => hasCoreEntries(root, dir)))
  return checks.every(Boolean)
}

export function Sidebar(): JSX.Element | null {
  const {
    projectPath,
    pathlyRoot,
    pathlyUserHome,
    projects,
    setPathlyUserHome,
    setPathlyRoot,
    activeTopic,
    setActiveTopic,
    sidebarCollapsed,
    setSidebarCollapsed,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    setSkillNotebookPath,
    skillNotebookViewMode,
    setSkillNotebookViewMode,
    dirtyItems,
    activePanel,
    setLastUsedFlowPath,
  } = useStore()

  const insertFragment = useSkillNotebookStore((s) => s.insertFragment)
  const insertBodyCell = useSkillNotebookStore((s) => s.insertBodyCell)
  const notebookCells  = useSkillNotebookStore((s) => s.cells)

  const { sections, setSections, loadItems, customWorkspaceSections } = useProjectFiles()
  const { planFolders, setPlanFolders, loadPlanFiles } = usePlanFiles()

  useEffect(() => {
    if (pathlyUserHome) return
    const fn = window.pathly.fs.userHome
    if (typeof fn !== 'function') return
    fn().then(setPathlyUserHome).catch(() => {})
  }, [pathlyUserHome, setPathlyUserHome])

  // The Library tab is Pathly's bundled/core library, not whichever saved project
  // happens to expose a partial src/pathly_data/core folder.
  useEffect(() => {
    let cancelled = false
    const probe = async (): Promise<void> => {
      const appRoot = typeof window.pathly.fs.appRoot === 'function'
        ? await window.pathly.fs.appRoot().catch(() => '')
        : ''
      const candidates = [
        ...(appRoot ? [appRoot] : []),
        ...(projectPath ? [projectPath] : []),
        ...(pathlyRoot ? [pathlyRoot] : []),
        ...projects.map((p) => p.path),
      ]
      const seen = new Set<string>()
      const unique = candidates.filter((p) => {
        if (seen.has(p)) return false
        seen.add(p)
        return true
      })
      for (const p of unique) {
        if (!cancelled && await isPathlyCoreRoot(p)) {
          if (p !== pathlyRoot) setPathlyRoot(p)
          return
        }
      }
    }
    void probe()
    return () => { cancelled = true }
  }, [pathlyRoot, projectPath, projects, setPathlyRoot])

  const activePanelUi = useUiStore((s) => s.activePanel)

  const { sidebarRef, onDragStart } = useSidebarResize()
  const windowWidth = useWindowWidth()

  const [planOpen, setPlanOpen]       = useState(true)
  const [filter, setFilter]           = useState('')
  const [libraryOpen, setLibraryOpen] = useState<boolean>(() => {
    try { return localStorage.getItem('pathly:sidebarTab') !== 'workspace' }
    catch { return true }
  })
  const [showFlowWizard, setShowFlowWizard]       = useState(false)
  const [showNewItemDialog, setShowNewItemDialog] = useState(false)
  const [newItemTarget, setNewItemTarget] = useState<{ type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null>(null)
  const [renamingPath, setRenamingPath] = useState<string | null>(null)
  const [renameValue, setRenameValue]   = useState('')
  const [confirmDelete, setConfirmDelete] = useState<PathlyItem | null>(null)
  const [confirmDeleteFolder, setConfirmDeleteFolder] = useState<string | null>(null)
  const [confirmDeleteSection, setConfirmDeleteSection] = useState<{ dir: string; name: string } | null>(null)
  const [dragOverPath, setDragOverPath] = useState<string | null>(null)
  const [splitModalItem, setSplitModalItem] = useState<CatalogItemData | null>(null)
  const [inlineCreate, setInlineCreate] = useState<{
    target: string   // 'workspace-root' | 'plan-folder' | 'plan-file' | section label
    parentDir: string
    type: 'file' | 'folder'
  } | null>(null)

  const dragFromGripRef = useRef(false)

  const deferredFilter = useDeferredValue(filter)
  const lowerFilter = deferredFilter.toLowerCase()


  const isNarrow = windowWidth < POPOVER_BREAKPOINT

  // Narrow + collapsed → completely hidden (TopBar toggle re-opens as popover)
  if (sidebarCollapsed && isNarrow) return null

  // Wide + collapsed → icon strip (no layout impact, thin rail)
  if (sidebarCollapsed && !isNarrow) {
    const openTab = (tab: 'library' | 'workspace'): void => {
      setSidebarCollapsed(false)
      setLibraryOpen(tab === 'library')
      setFilter('')
      try { localStorage.setItem('pathly:sidebarTab', tab) } catch { /* ignore */ }
    }
    return (
      <IconStrip
        activePanel={activePanel}
        libraryOpen={libraryOpen}
        onExpand={() => setSidebarCollapsed(false)}
        onWorkspace={() => openTab('workspace')}
        onLibrary={() => openTab('library')}
        onMonitor={() => setActivePanel('monitor')}
        onDbExplorer={() => setActivePanel('db-explorer')}
        onSettings={() => setActivePanel('settings')}
      />
    )
  }

  function toggleSection(label: string): void {
    setSections((prev) => ({ ...prev, [label]: { ...prev[label], open: !prev[label].open } }))
  }

  function toggleSubdir(sectionLabel: string, idx: number): void {
    setSections((prev) => {
      const section = prev[sectionLabel]
      if (!section.subdirs) return prev
      const subdirs = section.subdirs.map((sd, i) => i === idx ? { ...sd, open: !sd.open } : sd)
      return { ...prev, [sectionLabel]: { ...section, subdirs } }
    })
  }

  function handleItemClick(item: PathlyItem): void {
    setSelectedItem(item)
    if (item.type === 'flow') {
      setActivePanel('flow')
      setLastUsedFlowPath(item.path)
    } else if (item.path.endsWith('.md')) {
      setActivePanel('skill-notebook')
      setSkillNotebookPath(item.path)
    } else {
      setActivePanel('editor')
    }
  }

  function handleNewUserLibraryItem(section: Section, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!pathlyUserHome) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type as 'skill' | 'agent' | 'template' | 'debug' | 'explore', dir: `${pathlyUserHome}/${section.dir}` })
      setShowNewItemDialog(true)
    }
  }

  function handleInlineCreateFile(section: { label: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], open: true } }))
    setInlineCreate({ target: section.dir, parentDir: `${projectPath}/${section.dir}`, type: 'file' })
  }

  function handleInlineCreateFolder(section: { label: string; dir: string }, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], open: true } }))
    setInlineCreate({ target: section.dir, parentDir: `${projectPath}/${section.dir}`, type: 'folder' })
  }

  function handleInlineCreateFileInFolder(folderPath: string): void {
    setInlineCreate({ target: folderPath, parentDir: folderPath, type: 'file' })
  }

  function handleInlineCreateFolderInFolder(folderPath: string): void {
    setInlineCreate({ target: folderPath, parentDir: folderPath, type: 'folder' })
  }

  function handleCreateTopLevelFolder(e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setInlineCreate({ target: 'workspace-root', parentDir: `${projectPath}/pathly`, type: 'folder' })
  }

  function handleInlineCreatePlan(e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setInlineCreate({ target: 'plan-folder', parentDir: `${projectPath}/pathly/plans`, type: 'folder' })
  }

  function handleCreatePlanFile(e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath || !activeTopic) return
    setInlineCreate({ target: 'plan-file', parentDir: `${projectPath}/pathly/plans/${activeTopic}`, type: 'file' })
  }

  async function handleInlineCreateSubmit(name: string): Promise<void> {
    if (!inlineCreate) return
    const trimmed = name.trim()
    setInlineCreate(null)
    if (!trimmed) return
    const { target, parentDir, type } = inlineCreate
    try {
      if (target === 'plan-folder') {
        await window.pathly.fs.write(`${parentDir}/${trimmed}/STATE.json`, JSON.stringify({ current: 'INIT' }))
        await loadItems()
        await loadPlanFiles()
      } else if (target === 'plan-file') {
        await window.pathly.fs.write(`${parentDir}/${trimmed}`, '')
        await loadPlanFiles()
      } else if (type === 'folder') {
        await window.pathly.fs.write(`${parentDir}/${trimmed}/.gitkeep`, '')
        await loadItems()
      } else {
        await window.pathly.fs.write(`${parentDir}/${trimmed}`, '')
        await loadItems()
      }
    } catch (err) {
      console.error('Create failed:', err)
    }
  }

  function handleInlineCreateCancel(): void {
    setInlineCreate(null)
  }

  function handleToggleFolder(name: string): void {
    setPlanFolders((prev) => prev.map((f) => f.name === name ? { ...f, open: !f.open } : f))
  }

  function handleTogglePlanSubdir(folderName: string, subdirName: string): void {
    setPlanFolders((prev) => prev.map((f) =>
      f.name === folderName
        ? { ...f, subdirs: f.subdirs.map((sd) => sd.name === subdirName ? { ...sd, open: !sd.open } : sd) }
        : f
    ))
  }

  function handleFolderClick(name: string): void {
    setActiveTopic(name)
    setActivePanel('plan')
  }

  function startRename(item: PathlyItem, _itemDir: string): void {
    const baseName = item.name.includes('.')
      ? item.name.slice(0, item.name.lastIndexOf('.'))
      : item.name
    setRenamingPath(item.path)
    setRenameValue(baseName)
  }

  async function commitRename(item: PathlyItem, itemDir: string): Promise<void> {
    const trimmed = renameValue.trim()
    if (!trimmed) { setRenamingPath(null); return }
    const ext = item.name.includes('.') ? item.name.slice(item.name.lastIndexOf('.')) : ''
    const newName = trimmed + ext
    if (newName === item.name) { setRenamingPath(null); return }
    const newPath = `${itemDir}/${newName}`
    const content = await window.pathly.fs.read(item.path).catch(() => '')
    try {
      await window.pathly.fs.write(newPath, content ?? '')
      await window.pathly.fs.delete(item.path)
    } catch (err) {
      console.error('Rename failed:', err)
    } finally {
      setRenamingPath(null)
      await loadItems()
    }
  }

  async function handleRenameFolder(oldPath: string, newName: string): Promise<void> {
    const trimmed = newName.trim()
    if (!trimmed) return
    const parentDir = oldPath.split('/').slice(0, -1).join('/')
    const newPath = `${parentDir}/${trimmed}`
    if (oldPath === newPath) return
    try {
      const files = await window.pathly.fs.list(oldPath).catch(() => [] as string[])
      if (files.length === 0) {
        await window.pathly.fs.write(`${newPath}/.gitkeep`, '')
        await window.pathly.fs.delete(`${oldPath}/.gitkeep`).catch(() => {})
      } else {
        for (const fname of files) {
          const content = await window.pathly.fs.read(`${oldPath}/${fname}`).catch(() => '')
          await window.pathly.fs.write(`${newPath}/${fname}`, content ?? '')
          await window.pathly.fs.delete(`${oldPath}/${fname}`)
        }
      }
      await window.pathly.fs.delete(oldPath).catch(() => {})
    } catch (err) {
      console.error('Rename folder failed:', err)
    }
    await loadItems()
  }

  function handleDeleteCustomSection(sectionDir: string): void {
    const name = sectionDir.split('/').pop() ?? sectionDir
    setConfirmDeleteSection({ dir: sectionDir, name })
  }

  async function doDeleteCustomSection(sectionDir: string): Promise<void> {
    if (!projectPath) return
    const sectionPath = `${projectPath}/${sectionDir}`
    try {
      const items = await window.pathly.fs.list(sectionPath).catch(() => [] as string[])
      for (const item of items) {
        const itemPath = `${sectionPath}/${item}`
        const subItems = await window.pathly.fs.list(itemPath).catch(() => [] as string[])
        for (const sub of subItems) {
          await window.pathly.fs.delete(`${itemPath}/${sub}`).catch(() => {})
        }
        await window.pathly.fs.delete(itemPath).catch(() => {})
      }
      await window.pathly.fs.delete(sectionPath).catch(() => {})
    } catch (err) {
      console.error('Delete section failed:', err)
    }
    setConfirmDeleteSection(null)
    await loadItems()
  }

  async function handleDeletePlanFolder(folderPath: string): Promise<void> {
    try {
      const files = await window.pathly.fs.list(folderPath).catch(() => [] as string[])
      for (const fname of files) {
        await window.pathly.fs.delete(`${folderPath}/${fname}`).catch(() => {})
      }
      await window.pathly.fs.delete(folderPath).catch(() => {})
      const folderName = folderPath.split('/').pop() ?? ''
      if (activeTopic === folderName) setActiveTopic(null)
    } catch (err) {
      console.error('Delete plan folder failed:', err)
    }
    await loadItems()
    await loadPlanFiles()
  }

  async function handleMoveFolder(sourcePath: string, targetSectionDir: string): Promise<void> {
    const folderName = sourcePath.split('/').pop() ?? ''
    if (!folderName) return
    const targetPath = `${targetSectionDir}/${folderName}`
    if (sourcePath === targetPath) return
    try {
      const files = await window.pathly.fs.list(sourcePath).catch(() => [] as string[])
      if (files.length === 0) {
        await window.pathly.fs.write(`${targetPath}/.gitkeep`, '')
      } else {
        for (const fname of files) {
          const content = await window.pathly.fs.read(`${sourcePath}/${fname}`).catch(() => '')
          await window.pathly.fs.write(`${targetPath}/${fname}`, content ?? '')
          await window.pathly.fs.delete(`${sourcePath}/${fname}`)
        }
      }
      await window.pathly.fs.delete(sourcePath).catch(() => {})
    } catch (err) {
      console.error('Move folder failed:', err)
    }
    await loadItems()
  }

  async function handleReorgDrop(sourcePath: string, targetDir: string, _sectionId: string): Promise<void> {
    const fileName = sourcePath.split('/').pop() ?? ''
    if (!fileName) return
    const targetPath = `${targetDir}/${fileName}`
    if (sourcePath === targetPath) return
    const content = await window.pathly.fs.read(sourcePath).catch(() => '')
    await window.pathly.fs.write(targetPath, content ?? '')
    await window.pathly.fs.delete(sourcePath)
    await loadItems()
  }

  async function handleDeleteFolder(folderPath: string): Promise<void> {
    try {
      const files = await window.pathly.fs.list(folderPath).catch(() => [] as string[])
      for (const fname of files) {
        await window.pathly.fs.delete(`${folderPath}/${fname}`).catch(() => {})
      }
      await window.pathly.fs.delete(folderPath).catch(() => {})
    } catch (err) {
      console.error('Delete folder failed:', err)
    }
    await loadItems()
  }

  async function doDelete(item: PathlyItem): Promise<void> {
    try {
      await window.pathly.fs.delete(item.path)
    } catch (err) {
      console.error('Delete failed:', err)
    } finally {
      setConfirmDelete(null)
      if (selectedItem?.path === item.path) setSelectedItem(null)
      await loadItems()
    }
  }

  function handleItemDragStart(e: React.DragEvent, item: PathlyItem, section: Section): void {
    const sectionName = section.type as 'skill' | 'agent' | 'flow' | 'template'
    const pathSegments = item.path.split('/').slice(-1)

    if (dragFromGripRef.current && (sectionName === 'skill' || sectionName === 'agent')) {
      const payload: PathlyCanvasDragItem = {
        dragType: 'canvas',
        name: item.name,
        section: sectionName === 'skill' ? 'skills' : 'agents',
        path: pathSegments,
      }
      e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
      e.dataTransfer.effectAllowed = 'copy'
    } else {
      const payload: PathlyReorgDragItem = {
        dragType: 'reorg',
        name: item.name,
        section: sectionName === 'skill' ? 'skills' : sectionName === 'agent' ? 'agents' : sectionName === 'flow' ? 'flows' : 'templates',
        path: pathSegments,
        type: 'file',
        sourcePath: item.path,
      }
      e.dataTransfer.setData(PATHLY_DRAG_MIME, JSON.stringify(payload))
      e.dataTransfer.effectAllowed = 'move'
    }
    dragFromGripRef.current = false
  }

  void dragOverPath

  function switchTab(tab: 'library' | 'workspace'): void {
    setLibraryOpen(tab === 'library')
    setFilter('')
    try { localStorage.setItem('pathly:sidebarTab', tab) } catch {}
  }

  function handleCollapseAll(): void {
    setPlanOpen(false)
    setPlanFolders((prev) => prev.map((f) => ({
      ...f,
      open: false,
      subdirs: f.subdirs.map((sd) => ({ ...sd, open: false })),
    })))
    setSections((prev) => {
      const next: typeof prev = {}
      for (const key in prev) {
        next[key] = {
          ...prev[key],
          open: false,
          subdirs: prev[key].subdirs?.map((sd) => ({ ...sd, open: false })) ?? prev[key].subdirs,
        }
      }
      return next
    })
  }

  async function deleteItemViaAPI(item: CatalogItemData, type: CatalogGroup['type']): Promise<void> {
    if (type === 'flow') {
      await fetch(`http://localhost:8765/flows/${encodeURIComponent(item.name)}`, { method: 'DELETE' })
    } else {
      await fetch(`http://localhost:8765/catalog/item?type=${type}&name=${encodeURIComponent(item.name)}`, { method: 'DELETE' })
    }
  }

  async function createNewCatalogItem(type: CatalogGroup['type'], category?: string, name?: string): Promise<void> {
    if (!name?.trim()) return
    await fetch('http://localhost:8765/catalog/item/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: name.trim(), category: category || '' }),
    })
  }

  async function moveCatalogItem(item: CatalogItemData, type: CatalogGroup['type'], newCategory: string): Promise<void> {
    const res = await fetch('http://localhost:8765/catalog/item/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: item.name, newCategory }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Move failed (${res.status})`)
    }
  }

  async function renameCatalogItem(item: CatalogItemData, type: CatalogGroup['type'], newStem: string): Promise<void> {
    const res = await fetch('http://localhost:8765/catalog/item/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, name: item.name, newName: newStem }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Rename failed (${res.status})`)
    }
  }

  async function renameCatalogCategory(type: CatalogGroup['type'], oldName: string, newName: string): Promise<void> {
    const res = await fetch('http://localhost:8765/catalog/category/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, oldName, newName }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { error?: string }
      throw new Error(body.error ?? `Rename failed (${res.status})`)
    }
  }

  const sidebarClass = isNarrow
    ? `${styles.sidebar} ${styles.popover}`
    : styles.sidebar

  return (
    <>
    {isNarrow && (
      <div
        className={styles.backdrop}
        onClick={() => setSidebarCollapsed(true)}
        aria-hidden="true"
      />
    )}
    <div ref={sidebarRef} className={sidebarClass}>
      <TabBar libraryOpen={libraryOpen} onSwitch={switchTab} />

      {!libraryOpen && (
        <FilterRow
          libraryOpen={libraryOpen}
          filter={filter}
          onChange={setFilter}
          onClear={() => setFilter('')}
          onCollapseAll={handleCollapseAll}
        />
      )}

      <div className={styles.treeContainer}>
        {libraryOpen && (
          <LibraryCatalog
            context={activePanelUi === 'skill-notebook' ? 'notebook' : 'canvas'}
            pathlyRoot={pathlyRoot}
            onOpenSkill={(path) => { setSkillNotebookPath(path); setActivePanel('skill-notebook') }}
            onOpenFlow={(pathOrName) => {
              const filename = pathOrName.replace(/\\/g, '/').split('/').pop() ?? pathOrName
              const name = filename.replace(/\.flow\.yaml$/i, '')
              setSelectedItem({ name, path: pathOrName, type: 'flow' })
              setActivePanel('flow')
              setLastUsedFlowPath(pathOrName)
            }}
            onInsertCell={(item) => {
              if (skillNotebookViewMode !== 'cells') setSkillNotebookViewMode('cells')
              const lastCell = notebookCells[notebookCells.length - 1]
              if (item.itemType === 'fragment') {
                insertFragment(item.name, lastCell?.id ?? null)
              } else if (item.path) {
                void window.pathly.fs.read(item.path).then(raw => {
                  insertBodyCell(item.name, raw ?? '', lastCell?.id ?? null)
                }).catch(() => {
                  insertBodyCell(item.name, '', lastCell?.id ?? null)
                })
              }
            }}
            onAddCells={(item) => setSplitModalItem(item)}
            onNewItem={async (type, category, name) => {
              if (type === 'flow') {
                setShowFlowWizard(true)
              } else {
                await createNewCatalogItem(type, category, name)
              }
            }}
            onDeleteItem={(item, type) => deleteItemViaAPI(item, type)}
            onMoveItem={(item, type, cat) => moveCatalogItem(item, type, cat)}
            onRenameItem={(item, type, stem) => renameCatalogItem(item, type, stem)}
            onRenameCategory={(type, old, n) => renameCatalogCategory(type, old, n)}
            onNewCategory={async (type, name) => {
              await fetch('http://localhost:8765/catalog/category/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, name }),
              })
            }}
            onDeleteCategory={async (type, category) => {
              await fetch(`http://localhost:8765/catalog/category?type=${type}&name=${encodeURIComponent(category)}`, { method: 'DELETE' })
            }}
          />
        )}

        {!libraryOpen && projectPath && (
          <WorkspacePanel
            sections={sections}
            projectPath={projectPath}
            selectedItem={selectedItem}
            dirtyItems={dirtyItems}
            filter={filter}
            lowerFilter={lowerFilter}
            activeTopic={activeTopic}
            planFolders={planFolders}
            renamingPath={renamingPath}
            renameValue={renameValue}
            inlineCreate={inlineCreate}
            onSelect={handleItemClick}
            onToggleSection={toggleSection}
            onToggleSubdir={toggleSubdir}
            onActivePanel={(p) => setActivePanel(p)}
            onCreateTopLevelFolder={handleCreateTopLevelFolder}
            onInlineCreateFile={handleInlineCreateFile}
            onInlineCreateFolder={handleInlineCreateFolder}
            onNewPlan={handleInlineCreatePlan}
            onCreatePlanFile={handleCreatePlanFile}
            onInlineCreateSubmit={(name) => { void handleInlineCreateSubmit(name) }}
            onInlineCreateCancel={handleInlineCreateCancel}
            onRenameChange={setRenameValue}
            onRenameCommit={(item, itemDir) => { void commitRename(item, itemDir) }}
            onRenameCancel={() => setRenamingPath(null)}
            onStartRename={startRename}
            onStartDelete={setConfirmDelete}
            planOpen={planOpen}
            onTogglePlan={() => setPlanOpen((v) => !v)}
            onToggleFolder={handleToggleFolder}
            onFolderClick={handleFolderClick}
            onRenameFolder={(oldPath, newName) => { void handleRenameFolder(oldPath, newName) }}
            onDeleteFolder={(folderPath) => setConfirmDeleteFolder(folderPath)}
            onDeletePlanFolder={(folderPath) => { void handleDeletePlanFolder(folderPath) }}
            onTogglePlanSubdir={handleTogglePlanSubdir}
            onDeleteCustomSection={(dir) => { void handleDeleteCustomSection(dir) }}
            onInlineCreateFileInFolder={handleInlineCreateFileInFolder}
            onInlineCreateFolderInFolder={handleInlineCreateFolderInFolder}
            onReorgDrop={(src, tgt, sid) => { void handleReorgDrop(src, tgt, sid) }}
            onMoveFolder={(src, tgt) => { void handleMoveFolder(src, tgt) }}
            customWorkspaceSections={customWorkspaceSections}
          />
        )}

        <BottomNav
          activePanel={activePanel}
          onMonitor={() => setActivePanel('monitor')}
          onDbExplorer={() => setActivePanel('db-explorer')}
          onSettings={() => setActivePanel('settings')}
        />
      </div>

      <BrightskyProfile />

      <div className={styles.resizeHandle} onMouseDown={onDragStart} role="separator" aria-orientation="vertical" aria-label="Resize sidebar" />

      <SidebarDialogs
        showFlowWizard={showFlowWizard}
        showNewItemDialog={showNewItemDialog}
        newItemTarget={newItemTarget}
        confirmDelete={confirmDelete}
        confirmDeleteFolder={confirmDeleteFolder}
        confirmDeleteSection={confirmDeleteSection}
        onFlowWizardClose={() => setShowFlowWizard(false)}
        onFlowWizardCreated={(filePath) => {
          setShowFlowWizard(false)
          setSections((prev) => ({ ...prev, UserFlows: { ...prev.UserFlows, open: true } }))
          loadItems().then(() => {
            if (filePath) {
              const item: PathlyItem = {
                name: filePath.split('/').pop() ?? '',
                path: filePath,
                type: 'flow',
              }
              setSelectedItem(item)
              setActivePanel('flow')
              setLastUsedFlowPath(filePath)
            }
          })
        }}
        onNewItemDialogClose={() => setShowNewItemDialog(false)}
        onNewItemDialogCreated={(item) => { setShowNewItemDialog(false); setSelectedItem(item); setActivePanel('editor'); void loadItems() }}
        onConfirmDeleteCancel={() => setConfirmDelete(null)}
        onConfirmDeleteConfirm={(item) => void doDelete(item)}
        onConfirmDeleteFolderCancel={() => setConfirmDeleteFolder(null)}
        onConfirmDeleteFolderConfirm={(folderPath) => { setConfirmDeleteFolder(null); void handleDeleteFolder(folderPath) }}
        onConfirmDeleteSectionCancel={() => setConfirmDeleteSection(null)}
        onConfirmDeleteSectionConfirm={(dir) => void doDeleteCustomSection(dir)}
      />

      {splitModalItem?.path && (
        <SkillSplitModal
          filePath={splitModalItem.path}
          fileName={splitModalItem.name}
          onClose={() => setSplitModalItem(null)}
          onInsertOne={(raw) => {
            setSplitModalItem(null)
            if (skillNotebookViewMode !== 'cells') setSkillNotebookViewMode('cells')
            const lastCell = notebookCells[notebookCells.length - 1]
            insertBodyCell(splitModalItem.name, raw, lastCell?.id ?? null)
          }}
          onConfirm={(cells) => {
            setSplitModalItem(null)
            if (skillNotebookViewMode !== 'cells') setSkillNotebookViewMode('cells')
            let lastId = notebookCells[notebookCells.length - 1]?.id ?? null
            for (const cell of cells) {
              lastId = insertBodyCell(cell.heading, cell.content, lastId)
            }
          }}
        />
      )}
    </div>
    </>
  )
}
