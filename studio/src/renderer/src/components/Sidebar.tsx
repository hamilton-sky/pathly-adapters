import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import type { PathlyItem, PathlyItemType } from '../types'
import { FlowWizard } from './FlowWizard'
import { NewItemDialog } from './NewItemDialog'
import styles from './Sidebar.module.css'

interface TemplateSubdir {
  name: string
  open: boolean
  files: PathlyItem[]
}

interface SectionState {
  items: PathlyItem[]
  open: boolean
  subdirs?: TemplateSubdir[]
}

interface ConvRow {
  num: number
  title: string
  status: string
}

interface Section {
  label: string
  type: PathlyItemType
  dir: string
}

const SECTIONS: Section[] = [
  { label: 'Flows',     type: 'flow',     dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',    type: 'skill',    dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',    type: 'agent',    dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates', type: 'template', dir: 'src/pathly_data/core/templates' },
]

function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  let headerParsed = false
  for (const line of md.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('|')) continue
    const parts = trimmed.split('|').map((p) => p.trim()).filter(Boolean)
    if (!headerParsed) { headerParsed = true; continue }
    if (parts[0]?.startsWith('---')) continue
    const num = parseInt(parts[0], 10)
    if (isNaN(num)) continue
    const status = parts[parts.length - 1] ?? ''
    rows.push({ num, title: parts[1] ?? '', status: status.toUpperCase() })
  }
  return rows
}

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

  const [sections, setSections] = useState<Record<string, SectionState>>({
    Flows:     { items: [], open: false },
    Skills:    { items: [], open: false },
    Agents:    { items: [], open: false },
    Templates: { items: [], open: true  },
  })
  const [planConvs, setPlanConvs]     = useState<ConvRow[]>([])
  const [planOpen, setPlanOpen]       = useState(true)
  const [filter, setFilter]           = useState('')
  const [showFlowWizard, setShowFlowWizard]       = useState(false)
  const [showNewItemDialog, setShowNewItemDialog] = useState(false)
  const [newItemTarget, setNewItemTarget] = useState<{ type: PathlyItemType; dir: string } | null>(null)

  const loadItemsRef = useRef<() => Promise<void>>(async () => {})

  useEffect(() => {
    if (!projectPath) return
    async function loadItems(): Promise<void> {
      for (const section of SECTIONS) {
        try {
          const dir = `${projectPath}/${section.dir}`
          if (section.type === 'template') {
            const subdirNames = await window.pathly.fs.listDirs(dir)
            const subdirs: TemplateSubdir[] = []
            for (const subdirName of subdirNames) {
              const subdirPath = `${dir}/${subdirName}`
              let files: PathlyItem[] = []
              try {
                const fileNames = await window.pathly.fs.list(subdirPath)
                files = fileNames.map((fname) => ({ name: fname, path: `${subdirPath}/${fname}`, type: 'template' as const }))
              } catch { /* empty subdir */ }
              subdirs.push({ name: subdirName, open: false, files })
            }
            setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [], subdirs } }))
          } else {
            const names = await window.pathly.fs.list(`${projectPath}/${section.dir}`)
            const items: PathlyItem[] = names.map((name) => ({
              name, path: `${projectPath}/${section.dir}/${name}`, type: section.type,
            }))
            setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items } }))
          }
        } catch {
          setSections((prev) => ({ ...prev, [section.label]: { ...prev[section.label], items: [] } }))
        }
      }
    }
    loadItemsRef.current = loadItems
    loadItems()
  }, [projectPath])

  useEffect(() => {
    if (!projectPath || !activeTopic) { setPlanConvs([]); return }
    async function loadPlan(): Promise<void> {
      try {
        const md = await window.pathly.fs.read(`${projectPath}/pathly/plans/${activeTopic}/PROGRESS.md`)
        setPlanConvs(parseProgressMd(md))
      } catch { setPlanConvs([]) }
    }
    loadPlan()
  }, [projectPath, activeTopic])

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
    if (section.type === 'flow') {
      setShowFlowWizard(true)
    } else {
      setNewItemTarget({ type: section.type, dir: `${projectPath}/${section.dir}` })
      setShowNewItemDialog(true)
    }
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
        {/* Plan section */}
        <button className={styles.sectionHeader} onClick={() => setPlanOpen((v) => !v)}>
          <span className={styles.chevron}>{planOpen ? '▼' : '▶'}</span>
          PLAN
          <span className={styles.sectionSub}>[{activeTopic ?? 'no topic'}]</span>
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

        <div className={styles.divider} />

        {/* File sections */}
        {SECTIONS.map((section) => {
          const state = sections[section.label]

          if (section.type === 'template') {
            const subdirs = state.subdirs ?? []
            const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
            if (!hasMatch) return null
            return (
              <div key={section.label}>
                <button className={styles.sectionHeader} onClick={() => toggleSection(section.label)}>
                  <span className={styles.chevron}>{state.open ? '▼' : '▶'}</span>
                  {section.label.toUpperCase()}
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
                            return (
                              <button
                                key={item.path}
                                className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                                onClick={() => handleItemClick(item)}
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
              </button>
              {state.open && (
                <div>
                  {filtered.map((item) => {
                    const isDirty = dirtyItems.has(item.path)
                    const isSelected = selectedItem?.path === item.path
                    return (
                      <button
                        key={item.path}
                        className={`${styles.itemRow} ${isSelected ? styles.itemRowSelected : ''}`}
                        onClick={() => handleItemClick(item)}
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
            // Keep the Flows section open so the new flow is immediately visible
            setSections((prev) => ({ ...prev, Flows: { ...prev.Flows, open: true } }))
            // Reload file list, then select the newly created flow
            loadItemsRef.current().then(() => {
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
          type={newItemTarget.type as 'skill' | 'agent' | 'template'}
          dir={newItemTarget.dir}
          onClose={() => setShowNewItemDialog(false)}
          onCreated={(item) => { setShowNewItemDialog(false); setSelectedItem(item); setActivePanel('editor') }}
        />
      )}
    </div>
  )
}
