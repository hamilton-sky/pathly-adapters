import { useEffect, useDeferredValue, useRef, useState, useCallback } from 'react'
import { useStore } from '../../store'
import type { PathlyItem, PathlyCanvasDragItem, PathlyReorgDragItem } from '../../types'
import { PATHLY_DRAG_MIME } from '../../types'
import { useProjectFiles } from '../../hooks/useProjectFiles'
import { usePlanFiles } from '../../hooks/usePlanFiles'
import { FlowWizard } from '../FlowWizard'
import { NewItemDialog } from '../NewItemDialog'
import { DeleteConfirmModal } from './DeleteConfirmModal'
import { LibraryPanel } from './LibraryPanel'
import { WorkspacePanel } from './WorkspacePanel'
import type { Section } from './types'
import styles from './Sidebar.module.css'

export function Sidebar(): JSX.Element | null {
  const {
    projectPath,
    pathlyRoot,
    pathlyUserHome,
    setPathlyUserHome,
    activeTopic,
    setActiveTopic,
    sidebarCollapsed,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    dirtyItems,
    activePanel,
    setLastUsedFlowPath,
  } = useStore()

  const { sections, setSections, loadItems } = useProjectFiles()
  const { planFolders, setPlanFolders, loadPlanFiles } = usePlanFiles()

  useEffect(() => {
    if (pathlyUserHome) return
    const fn = window.pathly.fs.userHome
    if (typeof fn !== 'function') return
    fn().then(setPathlyUserHome).catch(() => {})
  }, [pathlyUserHome, setPathlyUserHome])

  const SIDEBAR_WIDTH_KEY = 'sidebar-width'
  const MIN_WIDTH = 180
  const MAX_WIDTH = 480

  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    const parsed = saved ? parseInt(saved, 10) : NaN
    return Number.isFinite(parsed) ? Math.min(Math.max(parsed, MIN_WIDTH), MAX_WIDTH) : 240
  })

  const isDraggingRef = useRef(false)
  const startXRef = useRef(0)
  const startWidthRef = useRef(0)

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    startXRef.current = e.clientX
    startWidthRef.current = sidebarWidth

    function onMouseMove(ev: MouseEvent): void {
      if (!isDraggingRef.current) return
      const delta = ev.clientX - startXRef.current
      const next = Math.min(Math.max(startWidthRef.current + delta, MIN_WIDTH), MAX_WIDTH)
      setSidebarWidth(next)
    }

    function onMouseUp(): void {
      isDraggingRef.current = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      setSidebarWidth((w) => { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w)); return w })
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [sidebarWidth])

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
  const [dragOverPath, setDragOverPath] = useState<string | null>(null)
  const [inlineCreate, setInlineCreate] = useState<{
    target: string   // 'workspace-root' | 'plan-folder' | 'plan-file' | section label
    parentDir: string
    type: 'file' | 'folder'
  } | null>(null)

  const dragFromGripRef = useRef(false)

  const deferredFilter = useDeferredValue(filter)
  const lowerFilter = deferredFilter.toLowerCase()

  if (sidebarCollapsed) return null

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
    setActivePanel(item.type === 'flow' ? 'flow' : 'editor')
    if (item.type === 'flow') {
      setLastUsedFlowPath(item.path)
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

  function handleInlineCreateFile(section: { dir: string }, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setInlineCreate({ target: section.dir, parentDir: `${projectPath}/${section.dir}`, type: 'file' })
  }

  function handleInlineCreateFolder(section: { dir: string }, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    setInlineCreate({ target: section.dir, parentDir: `${projectPath}/${section.dir}`, type: 'folder' })
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

  function switchTab(tab: 'library' | 'workspace'): void {
    setLibraryOpen(tab === 'library')
    setFilter('')
    try { localStorage.setItem('pathly:sidebarTab', tab) } catch {}
  }

  return (
    <div className={styles.sidebar} style={{ width: sidebarWidth }}>
      <div className={styles.tabBar} role="tablist" aria-label="Sidebar view">
        <button
          role="tab"
          aria-selected={!libraryOpen}
          className={`${styles.tab} ${!libraryOpen ? styles.tabActive : ''}`}
          onClick={() => switchTab('workspace')}
        >
          WORKSPACE
        </button>
        <button
          role="tab"
          aria-selected={libraryOpen}
          className={`${styles.tab} ${libraryOpen ? styles.tabActive : ''}`}
          onClick={() => switchTab('library')}
        >
          LIBRARY
        </button>
      </div>

      <div className={styles.filterRow}>
        <input
          className={styles.filterInput}
          placeholder={libraryOpen ? 'Search library…' : 'Filter…'}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {filter && (
          <button
            className={styles.filterClear}
            onClick={() => setFilter('')}
            title="Clear filter"
          >
            ×
          </button>
        )}
      </div>

      <div className={styles.treeContainer}>
        {libraryOpen && (
          <LibraryPanel
            sections={sections}
            selectedItem={selectedItem}
            filter={filter}
            lowerFilter={lowerFilter}
            renamingPath={renamingPath}
            renameValue={renameValue}
            onSelect={handleItemClick}
            onToggleSection={toggleSection}
            onToggleSubdir={toggleSubdir}
            onNewUserLibraryItem={handleNewUserLibraryItem}
            dragFromGripRef={dragFromGripRef}
            onDragStart={handleItemDragStart}
            onStartRename={startRename}
            onStartDelete={setConfirmDelete}
            onRenameChange={setRenameValue}
            onRenameCommit={(item, itemDir) => { void commitRename(item, itemDir) }}
            onRenameCancel={() => setRenamingPath(null)}
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
            onReorgDrop={(src, tgt, sid) => { void handleReorgDrop(src, tgt, sid) }}
            onRenameFolder={(oldPath, newName) => { void handleRenameFolder(oldPath, newName) }}
            onDeleteFolder={(folderPath) => { void handleDeleteFolder(folderPath) }}
          />
        )}

        <div className={styles.divider} />

        <button
          className={`${styles.bottomRow} ${activePanel === 'monitor' ? styles.bottomRowActive : ''}`}
          onClick={() => setActivePanel('monitor')}
        >
          <span className={styles.monitorDot}>●</span> Monitor
        </button>

        <button
          className={`${styles.bottomRow} ${activePanel === 'settings' ? styles.bottomRowActive : ''}`}
          onClick={() => setActivePanel('settings')}
        >
          ⚙ Settings
        </button>

        <div className={styles.divider} />
      </div>

      <div className={styles.resizeHandle} onMouseDown={onDragStart} role="separator" aria-orientation="vertical" aria-label="Resize sidebar" />

      {showFlowWizard && (
        <FlowWizard
          onClose={() => setShowFlowWizard(false)}
          onCreated={(filePath) => {
            setShowFlowWizard(false)
            setSections((prev) => ({ ...prev, Flows: { ...prev.Flows, open: true } }))
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
        />
      )}
      {showNewItemDialog && newItemTarget && (
        <NewItemDialog
          type={newItemTarget.type}
          dir={newItemTarget.dir}
          onClose={() => setShowNewItemDialog(false)}
          onCreated={(item) => { setShowNewItemDialog(false); setSelectedItem(item); setActivePanel('editor'); void loadItems() }}
        />
      )}

      {confirmDelete && (
        <DeleteConfirmModal
          item={confirmDelete}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => void doDelete(confirmDelete)}
        />
      )}
    </div>
  )
}
