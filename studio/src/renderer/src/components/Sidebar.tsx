import { useState, useEffect, useRef } from 'react'
import { useStore } from '../store'
import type { PathlyItem, PathlyItemType } from '../types'
import { useProjectFiles } from '../hooks/useProjectFiles'
import { usePlanConversations } from '../hooks/usePlanConversations'
import { FlowWizard } from './FlowWizard'
import { NewItemDialog } from './NewItemDialog'
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

interface ContextMenu {
  x: number
  y: number
  item: PathlyItem
  itemDir: string
}

export function Sidebar(): JSX.Element {
  const {
    projectPath,
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
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null)
  const contextMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!contextMenu) return
    function handleClick(e: MouseEvent): void {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [contextMenu])

  if (sidebarCollapsed) {
    return (
      <div className={styles.collapsed}>
        <button className={styles.expandBtn} onClick={() => setSidebarCollapsed(false)} title="Expand sidebar">►</button>
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
    if (!projectPath) return
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${projectPath}/${section.dir}` })
      setShowNewItemDialog(true)
    }
  }

  async function handleInlineCreate(section: Section, e: React.MouseEvent): Promise<void> {
    e.stopPropagation()
    if (!projectPath) return
    const name = window.prompt('Name:')
    if (!name || !name.trim()) return
    const trimmed = name.trim()

    if (section.type === 'flow') {
      setShowFlowWizard(true)
      return
    }

    if (section.type === 'debug' || section.type === 'explore') {
      const dirPath = `${projectPath}/${section.dir}/${trimmed}`
      await window.pathly.fs.write(`${dirPath}/STATE.json`, JSON.stringify({ current: 'INIT' }))
    } else {
      await window.pathly.fs.write(`${projectPath}/${section.dir}/${trimmed}.yaml`, '')
    }
    await loadItems()
  }

  async function handleInlineCreatePlan(e: React.MouseEvent): Promise<void> {
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
    setContextMenu(null)
    const currentName = item.name
    const newName = window.prompt('New name:', currentName)
    if (!newName || !newName.trim() || newName.trim() === currentName) return
    const trimmed = newName.trim()
    const ext = currentName.includes('.') ? currentName.slice(currentName.lastIndexOf('.')) : ''
    const newPath = `${itemDir}/${trimmed}${ext}`
    const content = await window.pathly.fs.read(item.path).catch(() => '')
    await window.pathly.fs.write(newPath, content ?? '')
    await window.pathly.fs.delete(item.path)
    await loadItems()
  }

  async function handleDelete(): Promise<void> {
    if (!contextMenu || !projectPath) return
    const { item } = contextMenu
    setContextMenu(null)
    if (!window.confirm(`Delete ${item.name}?`)) return
    await window.pathly.fs.delete(item.path)
    await loadItems()
  }

  const lowerFilter = filter.toLowerCase()

  const contextMenuStyle: React.CSSProperties = contextMenu ? {
    position: 'fixed',
    top: contextMenu.y,
    left: contextMenu.x,
    background: 'var(--bg-surface0)',
    border: '1px solid var(--bg-surface1)',
    borderRadius: '4px',
    zIndex: 9999,
    fontFamily: 'monospace',
    fontSize: '12px',
    padding: '4px 0',
    minWidth: '120px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
  } : {}

  const ctxItemStyle: React.CSSProperties = {
    display: 'block',
    width: '100%',
    background: 'none',
    border: 'none',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    padding: '5px 14px',
    textAlign: 'left',
    fontSize: '12px',
    fontFamily: 'monospace'
  }

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
                  <span className={styles.chevron}>{state.open ? '▼' : '▶'}</span>
                  {section.label.toUpperCase()}
                  {projectPath && (
                    <span
                      style={{ marginLeft: 'auto', paddingLeft: 8, color: 'var(--accent)', opacity: 0.7, fontSize: 13, lineHeight: 1 }}
                      onClick={(e) => { void handleInlineCreate(section, e) }}
                      title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                    >+</span>
                  )}
                </button>
                {state.open && (
                  <div>
                    {subdirs.map((subdir, idx) => {
                      const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                      if (filter && filteredFiles.length === 0) return null
                      return (
                        <div key={subdir.name}>
                          <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                            <span className={styles.chevron}>{subdir.open ? '▼' : '▶'}</span>
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
                    {!filter && (
                      <button className={styles.newBtn} onClick={() => handleNewItem(section)}>+ new template</button>
                    )}
                  </div>
                )}
              </div>
            )
          }

          const filtered = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
          if (filter && filtered.length === 0) return null
          return (
            <div key={section.label}>
              <button className={styles.sectionHeader} onClick={() => toggleSection(section.label)}>
                <span className={styles.chevron}>{state.open ? '▼' : '▶'}</span>
                {section.label.toUpperCase()}
                {projectPath && (
                  <span
                    style={{ marginLeft: 'auto', paddingLeft: 8, color: 'var(--accent)', opacity: 0.7, fontSize: 13, lineHeight: 1 }}
                    onClick={(e) => { void handleInlineCreate(section, e) }}
                    title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                  >+</span>
                )}
              </button>
              {state.open && (
                <div>
                  {filtered.map((item) => {
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
                        <span className={styles.itemName}>{item.name}</span>
                        {isDirty && <span className={styles.dirtyDot}>●</span>}
                      </button>
                    )
                  })}
                  {!filter && (
                    <button className={styles.newBtn} onClick={() => handleNewItem(section)}>+ new</button>
                  )}
                </div>
              )}
            </div>
          )
        })}

        {/* Section B — Workspace: only when a project is open */}
        {projectPath && (
          <>
            <div className={styles.divider} />

            {/* Plan section */}
            <button className={styles.sectionHeader} onClick={() => setPlanOpen((v) => !v)}>
              <span className={styles.chevron}>{planOpen ? '▼' : '▶'}</span>
              PLAN
              <span className={styles.sectionSub}>[{activeTopic ?? 'no topic'}]</span>
              <span
                style={{ marginLeft: 'auto', paddingLeft: 8, color: 'var(--accent)', opacity: 0.7, fontSize: 13, lineHeight: 1 }}
                onClick={(e) => { void handleInlineCreatePlan(e) }}
                title="New plan"
              >+</span>
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
                    <span className={styles.chevron}>{state.open ? '▼' : '▶'}</span>
                    {section.label.toUpperCase()}
                    <span
                      style={{ marginLeft: 'auto', paddingLeft: 8, color: 'var(--accent)', opacity: 0.7, fontSize: 13, lineHeight: 1 }}
                      onClick={(e) => { void handleInlineCreate(section, e) }}
                      title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                    >+</span>
                  </button>
                  {state.open && (
                    <div>
                      {subdirs.map((subdir, idx) => {
                        const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                        if (filter && filteredFiles.length === 0) return null
                        return (
                          <div key={subdir.name}>
                            <button className={styles.subdirHeader} onClick={() => toggleSubdir(section.label, idx)}>
                              <span className={styles.chevron}>{subdir.open ? '▼' : '▶'}</span>
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
                      {!filter && (
                        <button className={styles.newBtn} onClick={() => handleNewItem(section)}>
                          {section.type === 'explore' ? '+ new exploration' : '+ new debug'}
                        </button>
                      )}
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
        ◄
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
        <div ref={contextMenuRef} style={contextMenuStyle}>
          <button style={ctxItemStyle} onClick={() => { void handleRename() }}>Rename</button>
          <button style={{ ...ctxItemStyle, color: 'var(--red)' }} onClick={() => { void handleDelete() }}>Delete</button>
        </div>
      )}
    </div>
  )
}
