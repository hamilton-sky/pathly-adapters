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
    sectionLabel: string
    parentDir: string
    type: 'folder'
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
  }

  function handleNewUserLibraryItem(section: Section, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!pathlyUserHome) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${pathlyUserHome}/${section.dir}` })
      setShowNewItemDialog(true)
    }
  }

  function handleWorkspaceUserCreate(section: Section, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    if (!projectPath) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${projectPath}/${section.dir}` })
      setShowNewItemDialog(true)
    }
  }

  function handleInlineCreate(section: Section, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    const base = pathlyRoot || projectPath
    if (!base) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${base}/${section.dir}` })
      setShowNewItemDialog(true)
    }
  }

  async function handleInlineCreatePlan(e: React.MouseEvent<HTMLButtonElement>): Promise<void> {
    e.stopPropagation()
    if (!projectPath) return
    const name = window.prompt('Name:')
    if (!name || !name.trim()) return
    const trimmed = name.trim()
    await window.pathly.fs.write(`${projectPath}/pathly/plans/${trimmed}/STATE.json`, JSON.stringify({ current: 'INIT' }))
    await loadItems()
    await loadPlanFiles()
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

  // suppress unused warning — inlineCreate and dragOverPath are set but not yet rendered here
  void inlineCreate
  void dragOverPath

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
          aria-selected={libraryOpen}
          className={`${styles.tab} ${libraryOpen ? styles.tabActive : ''}`}
          onClick={() => switchTab('library')}
        >
          LIBRARY
        </button>
        <button
          role="tab"
          aria-selected={!libraryOpen}
          className={`${styles.tab} ${!libraryOpen ? styles.tabActive : ''}`}
          onClick={() => switchTab('workspace')}
        >
          WORKSPACE
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
            onSelect={handleItemClick}
            onToggleSection={toggleSection}
            onToggleSubdir={toggleSubdir}
            onActivePanel={(p) => setActivePanel(p)}
            onWorkspaceCreate={handleWorkspaceUserCreate}
            onInlineCreate={handleInlineCreate}
            onNewPlan={(e) => { void handleInlineCreatePlan(e) }}
            onRenameChange={setRenameValue}
            onRenameCommit={(item, itemDir) => { void commitRename(item, itemDir) }}
            onRenameCancel={() => setRenamingPath(null)}
            onStartRename={startRename}
            onStartDelete={setConfirmDelete}
            planOpen={planOpen}
            onTogglePlan={() => setPlanOpen((v) => !v)}
            onToggleFolder={handleToggleFolder}
            onFolderClick={handleFolderClick}
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
