import { useEffect, useDeferredValue, useRef, useState } from 'react'
import { ChevronRight, ChevronDown, Plus, GripVertical, FolderOpen, Folder, FileText, BookOpen, ArrowLeft } from 'lucide-react'
import { useStore } from '../store'
import type { PathlyItem, PathlyItemType, PathlyCanvasDragItem, PathlyReorgDragItem } from '../types'
import { PATHLY_DRAG_MIME } from '../types'
import { useProjectFiles } from '../hooks/useProjectFiles'
import { usePlanConversations } from '../hooks/usePlanConversations'
import { FlowWizard } from './FlowWizard'
import { NewItemDialog } from './NewItemDialog'
import { IconButton, Separator, ContextMenu } from './ui'
import styles from './Sidebar.module.css'

interface Section {
  label: string
  type: PathlyItemType
  dir: string
}

const PATHLY_SECTIONS: Section[] = [
  { label: 'Flows',     type: 'flow',     dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',    type: 'skill',    dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',    type: 'agent',    dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates', type: 'template', dir: 'src/pathly_data/core/templates' },
]

const USER_LIBRARY_SECTIONS: Section[] = [
  { label: 'UserAgents',    type: 'agent',    dir: 'agents'    },
  { label: 'UserSkills',    type: 'skill',    dir: 'skills'    },
  { label: 'UserTemplates', type: 'template', dir: 'templates' },
  { label: 'UserFlows',     type: 'flow',     dir: 'flows'     },
]

const USER_LIBRARY_DISPLAY_LABELS: Record<string, string> = {
  UserAgents: 'Agents', UserSkills: 'Skills', UserTemplates: 'Templates', UserFlows: 'Flows',
}

const WORKSPACE_USER_SECTIONS: Section[] = [
  { label: 'My Agents',    type: 'agent',    dir: 'pathly/agents'    },
  { label: 'My Skills',    type: 'skill',    dir: 'pathly/skills'    },
  { label: 'My Templates', type: 'template', dir: 'pathly/templates' },
  { label: 'My Flows',     type: 'flow',     dir: 'pathly/flows'     },
]

const WORKSPACE_FILE_SECTIONS: Section[] = [
  { label: 'Debugs',       type: 'debug',   dir: 'pathly/debugs'       },
  { label: 'Explorations', type: 'explore', dir: 'pathly/explorations' },
]

function convStatusClass(status: string): string {
  if (status === 'DONE') return styles.statusDone
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return styles.statusActive
  if (status === 'BLOCKED') return styles.statusBlocked
  return styles.statusDefault
}

function convIcon(status: string): string {
  if (status === 'DONE') return '✓'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '●'
  return '○'
}

interface ContextMenuState {
  x: number
  y: number
  item: PathlyItem
  itemDir: string
}

function InlineFolderInput({ onConfirm, onCancel }: {
  onConfirm: (name: string) => void
  onCancel: () => void
}): JSX.Element {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { inputRef.current?.focus() }, [])
  return (
    <div className={styles.inlineCreateRow}>
      <FolderOpen size={13} className={styles.inlineCreateIcon} />
      <input
        ref={inputRef}
        className={styles.inlineCreateInput}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); onConfirm(value) }
          if (e.key === 'Escape') { e.preventDefault(); onCancel() }
        }}
        onBlur={() => onConfirm(value)}
        placeholder="folder name"
        spellCheck={false}
      />
    </div>
  )
}

export function Sidebar(): JSX.Element | null {
  const {
    projectPath,
    pathlyRoot,
    pathlyUserHome,
    setPathlyUserHome,
    activeTopic,
    sidebarCollapsed,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    dirtyItems,
    activePanel,
  } = useStore()

  const { sections, setSections, loadItems } = useProjectFiles()
  const { planConvs } = usePlanConversations()

  useEffect(() => {
    if (pathlyUserHome) return
    const fn = window.pathly.fs.userHome
    if (typeof fn !== 'function') return
    fn().then(setPathlyUserHome).catch(() => {})
  }, [pathlyUserHome, setPathlyUserHome])

  const [planOpen, setPlanOpen]       = useState(true)
  const [filter, setFilter]           = useState('')
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [showFlowWizard, setShowFlowWizard]       = useState(false)
  const [showNewItemDialog, setShowNewItemDialog] = useState(false)
  const [newItemTarget, setNewItemTarget] = useState<{ type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [dragOverPath, setDragOverPath] = useState<string | null>(null)
  const [inlineCreate, setInlineCreate] = useState<{
    sectionLabel: string
    parentDir: string
    type: 'folder'
  } | null>(null)

  // Tracks whether the current drag was initiated from the canvas grip (⠿)
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

  function handleNewItem(section: Section): void {
    const base = pathlyRoot || projectPath
    if (!base) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${base}/${section.dir}` })
      setShowNewItemDialog(true)
    }
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

  function handleInlineCreateFolder(section: Section, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    const base = pathlyRoot || projectPath
    if (!base) return
    setInlineCreate({ sectionLabel: section.label, parentDir: `${base}/${section.dir}`, type: 'folder' })
  }

  function handleSubdirCreateFile(section: Section, subdirName: string, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    const base = pathlyRoot || projectPath
    if (!base) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${base}/${section.dir}/${subdirName}` })
      setShowNewItemDialog(true)
    }
  }

  function handleSubdirCreateFolder(section: Section, subdirName: string, e: React.MouseEvent<HTMLButtonElement>): void {
    e.stopPropagation()
    const base = pathlyRoot || projectPath
    if (!base) return
    setInlineCreate({ sectionLabel: section.label, parentDir: `${base}/${section.dir}/${subdirName}`, type: 'folder' })
  }

  async function handleInlineCreatePlan(e: React.MouseEvent<HTMLButtonElement>): Promise<void> {
    e.stopPropagation()
    if (!projectPath) return
    const name = window.prompt('Name:')
    if (!name || !name.trim()) return
    const trimmed = name.trim()
    await window.pathly.fs.write(`${projectPath}/pathly/plans/${trimmed}/STATE.json`, JSON.stringify({ current: 'INIT' }))
    await loadItems()
  }

  function handleContextMenu(e: React.MouseEvent, item: PathlyItem, itemDir: string): void {
    e.preventDefault()
    e.stopPropagation()
    setContextMenu({ x: e.clientX, y: e.clientY, item, itemDir })
  }

  async function handleRename(): Promise<void> {
    if (!contextMenu || !projectPath) return
    const { item, itemDir } = contextMenu
    const currentName = item.name
    const newName = window.prompt('New name:', currentName)
    if (!newName || !newName.trim() || newName.trim() === currentName) return
    const trimmed = newName.trim()
    const ext = currentName.includes('.') ? currentName.slice(currentName.lastIndexOf('.')) : ''
    const newPath = `${itemDir}/${trimmed}${ext}`
    const content = await window.pathly.fs.read(item.path).catch(() => '')
    try {
      await window.pathly.fs.write(newPath, content ?? '')
      await window.pathly.fs.delete(item.path)
    } catch (err) {
      console.error('Rename failed:', err)
      alert(`Failed to rename ${item.name}. The file may exist at both the old and new path.`)
    } finally {
      await loadItems()
    }
  }

  async function handleDelete(): Promise<void> {
    if (!contextMenu || !projectPath) return
    const { item } = contextMenu
    if (!window.confirm(`Delete ${item.name}?`)) return
    try {
      await window.pathly.fs.delete(item.path)
    } catch (err) {
      console.error('Delete failed:', err)
      alert(`Failed to delete ${item.name}.`)
    } finally {
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

  function handleGripPointerDown(): void {
    dragFromGripRef.current = true
  }

  function handleFolderDragOver(e: React.DragEvent, folderPath: string, folderSection: string): void {
    const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
    if (!raw) {
      // During dragover, getData may be empty; allow but check type attr
      const types = e.dataTransfer.types
      if (!types.includes(PATHLY_DRAG_MIME)) return
    }
    try {
      if (raw) {
        const payload = JSON.parse(raw) as { dragType: string; section: string }
        if (payload.dragType !== 'reorg') return
        if (payload.section !== folderSection) return
      }
    } catch { return }
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverPath(folderPath)
  }

  function handleFolderDragLeave(): void {
    setDragOverPath(null)
  }

  async function handleFolderDrop(e: React.DragEvent, folderSection: string, folderPath: string): Promise<void> {
    setDragOverPath(null)
    const raw = e.dataTransfer.getData(PATHLY_DRAG_MIME)
    if (!raw) return
    try {
      const payload = JSON.parse(raw) as { dragType: string; section: string }
      if (payload.dragType !== 'reorg') return
      if (payload.section !== folderSection) return
      e.preventDefault()
      const reorgPayload = payload as PathlyReorgDragItem
      const { sourcePath, name } = reorgPayload
      if (!sourcePath) return
      const destPath = `${folderPath}/${name}`
      if (sourcePath === destPath) return
      try {
        const content = await window.pathly.fs.read(sourcePath)
        await window.pathly.fs.write(destPath, content ?? '')
        await window.pathly.fs.delete(sourcePath)
        await loadItems()
      } catch (err) {
        console.error('Reorg move failed:', err)
      }
    } catch { /* ignore malformed payload */ }
  }

  return (
    <div className={styles.sidebar}>
      <div className={styles.filterRow}>
        <input className={styles.filterInput} placeholder={libraryOpen ? 'Search library…' : 'Filter…'} value={filter} onChange={(e) => setFilter(e.target.value)} />
        <button
          className={`${styles.libraryBtn} ${libraryOpen ? styles.libraryBtnActive : ''}`}
          onClick={() => { setLibraryOpen(v => !v); setFilter('') }}
          title={libraryOpen ? 'Back to workspace' : 'Browse library'}
        >
          {libraryOpen ? <ArrowLeft size={13} /> : <BookOpen size={13} />}
        </button>
      </div>

      <div className={styles.treeContainer}>
        {/* Library mode — Flows / Skills / Agents / Templates (read-only) */}
        {libraryOpen && (
          <>
            <div className={styles.libraryHeader}><BookOpen size={12} />Library</div>
            {PATHLY_SECTIONS.map((section) => {
              const state = sections[section.label]

              if (section.type === 'template') {
                if (state.subdirs === null) return null
                const subdirs = state.subdirs ?? []
                const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
                if (!hasMatch) return null
                return (
                  <div key={section.label}>
                    <div className={styles.sectionRow}>
                      <button className={styles.sectionToggle} onClick={() => toggleSection(section.label)}>
                        <span className={styles.chevron}>
                          {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        </span>
                        {section.label}
                      </button>
                    </div>
                    {state.open && (
                      <div>
                        {subdirs.map((subdir, idx) => {
                          const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                          if (filter && filteredFiles.length === 0) return null
                          return (
                            <div key={subdir.name}>
                              <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                                <span className={styles.chevron}>
                                  {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                                </span>
                                <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                                <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                              </button>
                              {subdir.open && filteredFiles.map((item) => {
                                const isSelected = selectedItem?.path === item.path
                                return (
                                  <button
                                    key={item.path}
                                    className={`${styles.systemItemRow} ${styles.systemItemRowDeep} ${isSelected ? styles.systemItemRowSelected : ''}`}
                                    onClick={() => handleItemClick(item)}
                                    title={item.path}
                                  >
                                    <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                    <span className={styles.itemName}>{item.name}</span>
                                  </button>
                                )
                              })}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              }

              const subdirs = state.subdirs ?? []
              const filtered = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
              const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
              if (filter && filtered.length === 0 && !hasSubdirMatch) return null
              return (
                <div key={section.label}>
                  <div className={styles.sectionRow}>
                    <button className={styles.sectionToggle} onClick={() => toggleSection(section.label)}>
                      <span className={styles.chevron}>
                        {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      </span>
                      {section.label}
                    </button>
                  </div>
                  {state.open && (
                    <div>
                      {subdirs.map((subdir, idx) => {
                        const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                        if (filter && filteredFiles.length === 0) return null
                        return (
                          <div key={subdir.name}>
                            <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                              <span className={styles.chevron}>
                                {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              </span>
                              <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                              <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                            </button>
                            {subdir.open && filteredFiles.map((item) => {
                              const isSelected = selectedItem?.path === item.path
                              const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                              return (
                                <button
                                  key={item.path}
                                  className={`${styles.systemItemRow} ${styles.systemItemRowDeep} ${isSelected ? styles.systemItemRowSelected : ''}`}
                                  draggable={isCanvasDraggable}
                                  onClick={() => handleItemClick(item)}
                                  onDragStart={isCanvasDraggable ? (e) => {
                                    dragFromGripRef.current = true
                                    handleItemDragStart(e, item, section)
                                  } : undefined}
                                  title={item.path}
                                >
                                  {isCanvasDraggable && (
                                    <span
                                      className={styles.grip}
                                      onPointerDown={handleGripPointerDown}
                                      title="Drag to canvas"
                                    >
                                      <GripVertical size={12} />
                                    </span>
                                  )}
                                  <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                  <span className={styles.itemName}>{item.name}</span>
                                </button>
                              )
                            })}
                          </div>
                        )
                      })}
                      {filtered.map((item) => {
                        const isSelected = selectedItem?.path === item.path
                        const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                        return (
                          <button
                            key={item.path}
                            className={`${styles.systemItemRow} ${isSelected ? styles.systemItemRowSelected : ''}`}
                            draggable={isCanvasDraggable}
                            onClick={() => handleItemClick(item)}
                            onDragStart={isCanvasDraggable ? (e) => {
                              dragFromGripRef.current = true
                              handleItemDragStart(e, item, section)
                            } : undefined}
                            title={item.path}
                          >
                            {isCanvasDraggable && (
                              <span
                                className={styles.grip}
                                onPointerDown={handleGripPointerDown}
                                title="Drag to canvas"
                              >
                                <GripVertical size={12} />
                              </span>
                            )}
                            <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                            <span className={styles.itemName}>{item.name}</span>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}

            {/* MY LIBRARY — user's global ~/.pathly files */}
            <div className={styles.libraryHeader} style={{ marginTop: 8 }}>MY LIBRARY</div>
            {USER_LIBRARY_SECTIONS.map((section) => {
              const stateKey = section.label
              const displayLabel = USER_LIBRARY_DISPLAY_LABELS[stateKey] ?? stateKey
              const state = sections[stateKey]
              if (!state) return null

              if (section.type === 'template') {
                const subdirs = state.subdirs ?? []
                const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
                if (filter && !hasMatch) return null
                return (
                  <div key={stateKey}>
                    <div className={styles.sectionRow}>
                      <button className={styles.sectionToggle} onClick={() => toggleSection(stateKey)}>
                        <span className={styles.chevron}>
                          {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                        </span>
                        {displayLabel}
                      </button>
                      <div className={styles.sectionActions}>
                        <IconButton onClick={(e) => handleNewUserLibraryItem(section, e)} title={`New ${displayLabel.slice(0, -1).toLowerCase()}`}>
                          <Plus size={12} />
                        </IconButton>
                      </div>
                    </div>
                    {state.open && (
                      <div>
                        {subdirs.map((subdir, idx) => {
                          const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                          if (filter && filteredFiles.length === 0) return null
                          return (
                            <div key={subdir.name}>
                              <button className={styles.subdirHeader} onClick={() => toggleSubdir(stateKey, idx)}>
                                <span className={styles.chevron}>
                                  {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                                </span>
                                <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                                <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                              </button>
                              {subdir.open && filteredFiles.map((item) => {
                                const isSelected = selectedItem?.path === item.path
                                return (
                                  <button
                                    key={item.path}
                                    className={`${styles.systemItemRow} ${styles.systemItemRowDeep} ${isSelected ? styles.systemItemRowSelected : ''}`}
                                    onClick={() => handleItemClick(item)}
                                    title={item.path}
                                  >
                                    <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                    <span className={styles.itemName}>{item.name}</span>
                                  </button>
                                )
                              })}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              }

              const subdirs = state.subdirs ?? []
              const filtered = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
              const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
              if (filter && filtered.length === 0 && !hasSubdirMatch) return null
              return (
                <div key={stateKey}>
                  <div className={styles.sectionRow}>
                    <button className={styles.sectionToggle} onClick={() => toggleSection(stateKey)}>
                      <span className={styles.chevron}>
                        {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      </span>
                      {displayLabel}
                    </button>
                    <div className={styles.sectionActions}>
                      <IconButton onClick={(e) => handleNewUserLibraryItem(section, e)} title={`New ${displayLabel.slice(0, -1).toLowerCase()}`}>
                        <Plus size={12} />
                      </IconButton>
                    </div>
                  </div>
                  {state.open && (
                    <div>
                      {subdirs.map((subdir, idx) => {
                        const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                        if (filter && filteredFiles.length === 0) return null
                        return (
                          <div key={subdir.name}>
                            <button className={styles.subdirHeader} onClick={() => toggleSubdir(stateKey, idx)}>
                              <span className={styles.chevron}>
                                {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              </span>
                              <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                              <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                            </button>
                            {subdir.open && filteredFiles.map((item) => {
                              const isSelected = selectedItem?.path === item.path
                              const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                              return (
                                <button
                                  key={item.path}
                                  className={`${styles.systemItemRow} ${styles.systemItemRowDeep} ${isSelected ? styles.systemItemRowSelected : ''}`}
                                  draggable={isCanvasDraggable}
                                  onClick={() => handleItemClick(item)}
                                  onDragStart={isCanvasDraggable ? (e) => {
                                    dragFromGripRef.current = true
                                    handleItemDragStart(e, item, section)
                                  } : undefined}
                                  title={item.path}
                                >
                                  {isCanvasDraggable && (
                                    <span className={styles.grip} onPointerDown={handleGripPointerDown} title="Drag to canvas">
                                      <GripVertical size={12} />
                                    </span>
                                  )}
                                  <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                  <span className={styles.itemName}>{item.name}</span>
                                </button>
                              )
                            })}
                          </div>
                        )
                      })}
                      {filtered.map((item) => {
                        const isSelected = selectedItem?.path === item.path
                        const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                        return (
                          <button
                            key={item.path}
                            className={`${styles.systemItemRow} ${isSelected ? styles.systemItemRowSelected : ''}`}
                            draggable={isCanvasDraggable}
                            onClick={() => handleItemClick(item)}
                            onDragStart={isCanvasDraggable ? (e) => {
                              dragFromGripRef.current = true
                              handleItemDragStart(e, item, section)
                            } : undefined}
                            title={item.path}
                          >
                            {isCanvasDraggable && (
                              <span className={styles.grip} onPointerDown={handleGripPointerDown} title="Drag to canvas">
                                <GripVertical size={12} />
                              </span>
                            )}
                            <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                            <span className={styles.itemName}>{item.name}</span>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}

        {/* Section B — Workspace: only when a project is open and not in library mode */}
        {!libraryOpen && projectPath && (
          <>
            <Separator label="Workspace" />

            {/* Project-local user authoring sections */}
            {WORKSPACE_USER_SECTIONS.map((section) => {
              const state = sections[section.label]
              if (!state) return null
              const subdirs = state.subdirs ?? []
              const filteredItems = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
              const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
              if (filter && filteredItems.length === 0 && !hasSubdirMatch) return null
              return (
                <div key={section.label}>
                  <div className={styles.sectionRow}>
                    <button className={styles.sectionToggle} onClick={() => toggleSection(section.label)}>
                      <span className={styles.chevron}>
                        {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      </span>
                      {section.label}
                    </button>
                    <div className={styles.sectionActions}>
                      <IconButton
                        onClick={(e) => handleWorkspaceUserCreate(section, e)}
                        title={`New ${section.label.toLowerCase()}`}
                      >
                        <Plus size={12} />
                      </IconButton>
                    </div>
                  </div>
                  {state.open && (
                    <div>
                      {subdirs.map((subdir, idx) => {
                        const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                        if (filter && filteredFiles.length === 0) return null
                        return (
                          <div key={subdir.name}>
                            <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                              <span className={styles.chevron}>
                                {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              </span>
                              <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                              {subdir.name}/
                            </button>
                            {subdir.open && filteredFiles.map((item) => {
                              const isDirty = dirtyItems.has(item.path)
                              const isSelected = selectedItem?.path === item.path
                              const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                              return (
                                <button
                                  key={item.path}
                                  className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                                  onClick={() => handleItemClick(item)}
                                  onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                                  title={item.path}
                                >
                                  <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                  <span className={styles.itemName}>{item.name}</span>
                                  {isDirty && <span className={styles.dirtyDot}>●</span>}
                                </button>
                              )
                            })}
                          </div>
                        )
                      })}
                      {filteredItems.map((item) => {
                        const isDirty = dirtyItems.has(item.path)
                        const isSelected = selectedItem?.path === item.path
                        const itemDir = `${projectPath}/${section.dir}`
                        return (
                          <button
                            key={item.path}
                            className={`${styles.itemRow} ${isSelected ? styles.itemRowSelected : ''}`}
                            onClick={() => handleItemClick(item)}
                            onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                            title={item.path}
                          >
                            <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                            <span className={styles.itemName}>{item.name}</span>
                            {isDirty && <span className={styles.dirtyDot}>●</span>}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Plan section */}
            <div className={styles.sectionRow}>
              <button className={styles.sectionToggle} onClick={() => setPlanOpen((v) => !v)}>
                <span className={styles.chevron}>
                  {planOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                </span>
                Plan
                <span className={styles.sectionSub}>[{activeTopic ?? 'no topic'}]</span>
              </button>
              <div className={styles.sectionActions}>
                <IconButton
                  onClick={(e) => { void handleInlineCreatePlan(e) }}
                  title="New plan"
                >
                  <Plus size={12} />
                </IconButton>
              </div>
            </div>
            {planOpen && (
              <div>
                {planConvs.length === 0 ? (
                  <div className={styles.convEmpty}>No conversations</div>
                ) : (
                  planConvs.map((conv) => {
                    const cls = convStatusClass(conv.status)
                    return (
                      <button key={conv.num} className={styles.convRow} onClick={() => setActivePanel('plan')}>
                        <span className={`${cls} ${styles.convStatus}`} style={{ marginRight: 6, flexShrink: 0 }}>
                          {convIcon(conv.status)}
                        </span>
                        <span className={styles.convLabel}>Conv {conv.num} — {conv.title}</span>
                        <span className={`${styles.convStatus} ${cls}`}>{conv.status}</span>
                      </button>
                    )
                  })
                )}
              </div>
            )}

            {WORKSPACE_FILE_SECTIONS.map((section) => {
              const state = sections[section.label]
              if (state.subdirs === null) return null
              const subdirs = state.subdirs ?? []
              const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
              if (!hasMatch) return null
              return (
                <div key={section.label}>
                  <div className={styles.sectionRow}>
                    <button className={styles.sectionToggle} onClick={() => toggleSection(section.label)}>
                      <span className={styles.chevron}>
                        {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      </span>
                      {section.label}
                    </button>
                    <div className={styles.sectionActions}>
                      <IconButton
                        onClick={(e) => { void handleInlineCreate(section, e) }}
                        title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                      >
                        <Plus size={12} />
                      </IconButton>
                    </div>
                  </div>
                  {state.open && (
                    <div>
                      {subdirs.map((subdir, idx) => {
                        const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                        if (filter && filteredFiles.length === 0) return null
                        return (
                          <div key={subdir.name}>
                            <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                              <span className={styles.chevron}>
                                {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              </span>
                              <Folder size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                              {subdir.name}/
                            </button>
                            {subdir.open && filteredFiles.map((item) => {
                              const isDirty = dirtyItems.has(item.path)
                              const isSelected = selectedItem?.path === item.path
                              const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                              return (
                                <button
                                  key={item.path}
                                  className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                                  onClick={() => handleItemClick(item)}
                                  onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                                  title={item.path}
                                >
                                  <FileText size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                                  <span className={styles.itemName}>{item.name}</span>
                                  {isDirty && <span className={styles.dirtyDot}>●</span>}
                                </button>
                              )
                            })}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </>
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

      {contextMenu && (
        <ContextMenu
          position={{ x: contextMenu.x, y: contextMenu.y }}
          onClose={() => setContextMenu(null)}
          items={[
            { label: 'Rename', onClick: () => { void handleRename() } },
            { label: 'Delete', onClick: () => { void handleDelete() }, destructive: true },
          ]}
        />
      )}
    </div>
  )
}
