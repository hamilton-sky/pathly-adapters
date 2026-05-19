import { useRef, useState } from 'react'
import { ChevronRight, ChevronDown, Plus, FolderPlus, GripVertical } from 'lucide-react'
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

export function Sidebar(): JSX.Element {
  const {
    projectPath,
    pathlyRoot,
    activeTopic,
    sidebarCollapsed,
    setSidebarCollapsed,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    dirtyItems,
    activePanel,
  } = useStore()

  const { sections, setSections, loadItems } = useProjectFiles()
  const { planConvs } = usePlanConversations()

  const [planOpen, setPlanOpen]       = useState(true)
  const [filter, setFilter]           = useState('')
  const [showFlowWizard, setShowFlowWizard]       = useState(false)
  const [showNewItemDialog, setShowNewItemDialog] = useState(false)
  const [newItemTarget, setNewItemTarget] = useState<{ type: 'skill' | 'agent' | 'template' | 'debug' | 'explore'; dir: string } | null>(null)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [dragOverPath, setDragOverPath] = useState<string | null>(null)

  // Tracks whether the current drag was initiated from the canvas grip (⠿)
  const dragFromGripRef = useRef(false)

  if (sidebarCollapsed) {
    return (
      <div className={styles.collapsed}>
        <button className={styles.expandBtn} onClick={() => setSidebarCollapsed(false)} title="Expand sidebar">
          <ChevronRight size={13} />
        </button>
      </div>
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
    void handleCreateFolder(`${base}/${section.dir}`)
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
    void handleCreateFolder(`${base}/${section.dir}/${subdirName}`)
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

  async function handleCreateFolder(baseDir: string): Promise<void> {
    const name = window.prompt('Folder name:')
    if (!name || !name.trim()) return
    const trimmed = name.trim().replace(/[^a-zA-Z0-9_-]/g, '-')
    if (!trimmed) return
    try {
      await window.pathly.fs.write(`${baseDir}/${trimmed}/.gitkeep`, '')
      await loadItems()
    } catch (err) {
      console.error('Failed to create folder:', err)
    }
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

  const lowerFilter = filter.toLowerCase()

  return (
    <div className={styles.sidebar}>
      <div className={styles.filterRow}>
        <input
          className={styles.filterInput}
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div className={styles.treeContainer}>
        {/* Section A — Pathly: always visible */}
        {PATHLY_SECTIONS.map((section) => {
          const state = sections[section.label]

          if (section.type === 'template') {
            if (state.subdirs === null) return null
            const subdirs = state.subdirs ?? []
            const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
            if (!hasMatch) return null
            return (
              <div key={section.label}>
                <button className={styles.sectionHeader} onClick={() => toggleSection(section.label)}>
                  <span className={styles.chevron}>
                    {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  </span>
                  {section.label.toUpperCase()}
                  <div style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
                    <IconButton
                      onClick={(e) => { void handleInlineCreate(section, e) }}
                      title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                    >
                      <Plus size={12} />
                    </IconButton>
                    <IconButton
                      onClick={(e) => handleInlineCreateFolder(section, e)}
                      title="New folder"
                    >
                      <FolderPlus size={12} />
                    </IconButton>
                  </div>
                </button>
                {state.open && (
                  <div>
                    {subdirs.map((subdir, idx) => {
                      const base = pathlyRoot || projectPath || ''
                      const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                      if (filter && filteredFiles.length === 0) return null
                      return (
                        <div key={subdir.name}>
                          <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                            <span className={styles.chevron}>
                              {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                            </span>
                            <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                            <div style={{ display: 'flex', gap: 2 }} onClick={(e) => e.stopPropagation()}>
                              <IconButton onClick={(e) => handleSubdirCreateFile(section, subdir.name, e)} title={`New file in ${subdir.name}`}>
                                <Plus size={11} />
                              </IconButton>
                              <IconButton onClick={(e) => handleSubdirCreateFolder(section, subdir.name, e)} title={`New folder in ${subdir.name}`}>
                                <FolderPlus size={11} />
                              </IconButton>
                            </div>
                          </button>
                          {subdir.open && filteredFiles.map((item) => {
                            const isDirty = dirtyItems.has(item.path)
                            const isSelected = selectedItem?.path === item.path
                            const itemDir = `${base}/${section.dir}/${subdir.name}`
                            return (
                              <button
                                key={item.path}
                                className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                                draggable
                                onClick={() => handleItemClick(item)}
                                onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                                onDragStart={(e) => handleItemDragStart(e, item, section)}
                                title={item.path}
                              >
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
          }

          const subdirs = state.subdirs ?? []
          const filtered = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
          const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
          if (filter && filtered.length === 0 && !hasSubdirMatch) return null
          return (
            <div key={section.label}>
              <button className={styles.sectionHeader} onClick={() => toggleSection(section.label)}>
                <span className={styles.chevron}>
                  {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                </span>
                {section.label.toUpperCase()}
                <div style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
                  <IconButton
                    onClick={(e) => { void handleInlineCreate(section, e) }}
                    title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                  >
                    <Plus size={12} />
                  </IconButton>
                  <IconButton
                    onClick={(e) => handleInlineCreateFolder(section, e)}
                    title="New folder"
                  >
                    <FolderPlus size={12} />
                  </IconButton>
                </div>
              </button>
              {state.open && (
                <div>
                  {subdirs.map((subdir, idx) => {
                    const base = pathlyRoot || projectPath || ''
                    const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                    if (filter && filteredFiles.length === 0) return null
                    const folderPath = `${base}/${section.dir}/${subdir.name}`
                    const folderSection = section.type === 'skill' ? 'skills' : section.type === 'agent' ? 'agents' : section.type === 'flow' ? 'flows' : 'templates'
                    return (
                      <div
                        key={subdir.name}
                        onDragOver={(e) => handleFolderDragOver(e, folderPath, folderSection)}
                        onDragLeave={handleFolderDragLeave}
                        onDrop={(e) => { void handleFolderDrop(e, folderSection, folderPath) }}
                        style={dragOverPath === folderPath ? { borderLeft: '3px solid #8B5CF6' } : undefined}
                      >
                        <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                          <span className={styles.chevron}>
                            {subdir.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                          </span>
                          <span style={{ flex: 1, textAlign: 'left' }}>{subdir.name}/</span>
                          <div style={{ display: 'flex', gap: 2 }} onClick={(e) => e.stopPropagation()}>
                            <IconButton onClick={(e) => handleSubdirCreateFile(section, subdir.name, e)} title={`New file in ${subdir.name}`}>
                              <Plus size={11} />
                            </IconButton>
                            <IconButton onClick={(e) => handleSubdirCreateFolder(section, subdir.name, e)} title={`New folder in ${subdir.name}`}>
                              <FolderPlus size={11} />
                            </IconButton>
                          </div>
                        </button>
                        {subdir.open && filteredFiles.map((item) => {
                          const isDirty = dirtyItems.has(item.path)
                          const isSelected = selectedItem?.path === item.path
                          const itemDir = folderPath
                          const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                          return (
                            <button
                              key={item.path}
                              className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                              draggable
                              onClick={() => handleItemClick(item)}
                              onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                              onDragStart={(e) => handleItemDragStart(e, item, section)}
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
                              <span className={styles.itemName}>{item.name}</span>
                              {isDirty && <span className={styles.dirtyDot}>●</span>}
                            </button>
                          )
                        })}
                      </div>
                    )
                  })}
                  {filtered.map((item) => {
                    const isDirty = dirtyItems.has(item.path)
                    const isSelected = selectedItem?.path === item.path
                    const itemDir = `${projectPath}/${section.dir}`
                    const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'
                    return (
                      <button
                        key={item.path}
                        className={`${styles.itemRow} ${isSelected ? styles.itemRowSelected : ''}`}
                        draggable
                        onClick={() => handleItemClick(item)}
                        onContextMenu={(e) => handleContextMenu(e, item, itemDir)}
                        onDragStart={(e) => handleItemDragStart(e, item, section)}
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

        {/* Section B — Workspace: only when a project is open */}
        {projectPath && (
          <>
            <Separator label="Workspace" />

            {/* Plan section */}
            <button className={styles.sectionHeader} onClick={() => setPlanOpen((v) => !v)}>
              <span className={styles.chevron}>
                {planOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
              </span>
              PLAN
              <span className={styles.sectionSub}>[{activeTopic ?? 'no topic'}]</span>
              <IconButton
                style={{ marginLeft: 'auto' }}
                onClick={(e) => { void handleInlineCreatePlan(e) }}
                title="New plan"
              >
                <Plus size={12} />
              </IconButton>
            </button>
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
                  <button className={styles.sectionHeader} onClick={() => toggleSection(section.label)}>
                    <span className={styles.chevron}>
                      {state.open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                    </span>
                    {section.label.toUpperCase()}
                    <IconButton
                      style={{ marginLeft: 'auto' }}
                      onClick={(e) => { void handleInlineCreate(section, e) }}
                      title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                    >
                      <Plus size={12} />
                    </IconButton>
                  </button>
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

      <button className={styles.collapseBtn} onClick={() => setSidebarCollapsed(true)} title="Collapse sidebar">
        <ChevronRight size={13} style={{ transform: 'rotate(180deg)' }} />
      </button>

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
          onCreated={(item) => { setShowNewItemDialog(false); setSelectedItem(item); setActivePanel('editor') }}
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
