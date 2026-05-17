import { useEffect, useState } from 'react'
import { useStore } from '../store'
import type { PathlyItem, PathlyItemType } from '../types'

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
  { label: 'Flows', type: 'flow', dir: 'src/pathly_data/core/flows' },
  { label: 'Skills', type: 'skill', dir: 'src/pathly_data/core/skills' },
  { label: 'Agents', type: 'agent', dir: 'src/pathly_data/core/agents' },
  { label: 'Templates', type: 'template', dir: 'src/pathly_data/core/templates' }
]

function parseProgressMd(md: string): ConvRow[] {
  const rows: ConvRow[] = []
  for (const line of md.split('\n')) {
    const parts = line.split('|').map((p) => p.trim())
    if (parts.length < 5) continue
    const num = parseInt(parts[1], 10)
    if (isNaN(num)) continue
    rows.push({ num, title: parts[2], status: parts[4].toUpperCase() })
  }
  return rows
}

function convStatusColor(status: string): string {
  if (status === 'DONE') return '#a6e3a1'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '#89b4fa'
  if (status === 'BLOCKED') return '#f38ba8'
  return '#6c7086'
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
    activePanel
  } = useStore()

  const [sections, setSections] = useState<Record<string, SectionState>>({
    Flows: { items: [], open: false },
    Skills: { items: [], open: false },
    Agents: { items: [], open: false },
    Templates: { items: [], open: true }
  })
  const [planConvs, setPlanConvs] = useState<ConvRow[]>([])
  const [planOpen, setPlanOpen] = useState(true)
  const [filter, setFilter] = useState('')

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
                files = fileNames.map((fname) => ({
                  name: fname,
                  path: `${subdirPath}/${fname}`,
                  type: 'template' as const
                }))
              } catch {
                // empty subdir
              }
              subdirs.push({ name: subdirName, open: false, files })
            }
            setSections((prev) => ({
              ...prev,
              [section.label]: { ...prev[section.label], items: [], subdirs }
            }))
          } else {
            const names = await window.pathly.fs.list(`${projectPath}/${section.dir}`)
            const items: PathlyItem[] = names.map((name) => ({
              name,
              path: `${projectPath}/${section.dir}/${name}`,
              type: section.type
            }))
            setSections((prev) => ({
              ...prev,
              [section.label]: { ...prev[section.label], items }
            }))
          }
        } catch {
          setSections((prev) => ({
            ...prev,
            [section.label]: { ...prev[section.label], items: [] }
          }))
        }
      }
    }

    loadItems()
  }, [projectPath])

  useEffect(() => {
    if (!projectPath || !activeTopic) {
      setPlanConvs([])
      return
    }

    async function loadPlan(): Promise<void> {
      try {
        const md = await window.pathly.fs.read(
          `${projectPath}/pathly/plans/${activeTopic}/PROGRESS.md`
        )
        setPlanConvs(parseProgressMd(md))
      } catch {
        setPlanConvs([])
      }
    }

    loadPlan()
  }, [projectPath, activeTopic])

  if (sidebarCollapsed) {
    return (
      <div style={styles.collapsed}>
        <button
          style={styles.expandBtn}
          onClick={() => setSidebarCollapsed(false)}
          title="Expand sidebar"
        >
          ►
        </button>
      </div>
    )
  }

  function toggleSection(label: string): void {
    setSections((prev) => ({
      ...prev,
      [label]: { ...prev[label], open: !prev[label].open }
    }))
  }

  function toggleSubdir(sectionLabel: string, subdirIndex: number): void {
    setSections((prev) => {
      const section = prev[sectionLabel]
      if (!section.subdirs) return prev
      const subdirs = section.subdirs.map((sd, i) =>
        i === subdirIndex ? { ...sd, open: !sd.open } : sd
      )
      return { ...prev, [sectionLabel]: { ...section, subdirs } }
    })
  }

  function handleItemClick(item: PathlyItem): void {
    setSelectedItem(item)
    setActivePanel(item.type === 'flow' ? 'flow' : 'editor')
  }

  const lowerFilter = filter.toLowerCase()

  return (
    <div style={styles.sidebar}>
      <div style={styles.filterRow}>
        <input
          style={styles.filterInput}
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div style={styles.treeContainer}>
        {/* Plan section */}
        <button style={styles.sectionHeader} onClick={() => setPlanOpen((v) => !v)}>
          <span style={styles.chevron}>{planOpen ? '▼' : '▶'}</span>
          PLAN
          <span style={styles.sectionSub}>[{activeTopic ?? 'no topic'}]</span>
        </button>
        {planOpen && (
          <div>
            {planConvs.length === 0 ? (
              <div style={styles.convEmpty}>No conversations</div>
            ) : (
              planConvs.map((conv) => {
                const color = convStatusColor(conv.status)
                const icon =
                  conv.status === 'DONE'
                    ? '✓'
                    : conv.status === 'IN_PROGRESS' || conv.status === 'REVIEWING' || conv.status === 'BUILDING'
                      ? '●'
                      : '○'
                return (
                  <button
                    key={conv.num}
                    style={styles.convRow}
                    onClick={() => setActivePanel('plan')}
                  >
                    <span style={{ color, marginRight: '6px', flexShrink: 0 }}>{icon}</span>
                    <span style={styles.convLabel}>
                      Conv {conv.num} — {conv.title}
                    </span>
                    <span style={{ ...styles.convStatus, color }}>{conv.status}</span>
                  </button>
                )
              })
            )}
          </div>
        )}

        <div style={styles.divider} />

        {/* File sections */}
        {SECTIONS.map((section) => {
          const state = sections[section.label]

          if (section.type === 'template') {
            const subdirs = state.subdirs ?? []
            const hasMatch =
              !filter ||
              subdirs.some((sd) =>
                sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))
              )
            if (!hasMatch) return null

            return (
              <div key={section.label}>
                <button
                  style={styles.sectionHeader}
                  onClick={() => toggleSection(section.label)}
                >
                  <span style={styles.chevron}>{state.open ? '▼' : '▶'}</span>
                  {section.label.toUpperCase()}
                </button>
                {state.open && (
                  <div>
                    {subdirs.map((subdir, idx) => {
                      const filteredFiles = filter
                        ? subdir.files.filter((f) =>
                            f.name.toLowerCase().includes(lowerFilter)
                          )
                        : subdir.files
                      if (filter && filteredFiles.length === 0) return null

                      return (
                        <div key={subdir.name}>
                          <button
                            style={styles.subdirHeader}
                            onClick={() => toggleSubdir(section.label, idx)}
                          >
                            <span style={styles.chevron}>
                              {subdir.open ? '▼' : '▶'}
                            </span>
                            {subdir.name}/
                          </button>
                          {subdir.open && (
                            <div>
                              {filteredFiles.map((item) => {
                                const isDirty = dirtyItems.has(item.path)
                                const isSelected = selectedItem?.path === item.path
                                return (
                                  <button
                                    key={item.path}
                                    style={{
                                      ...styles.itemRow,
                                      paddingLeft: '44px',
                                      ...(isSelected ? styles.itemRowSelected : {})
                                    }}
                                    onClick={() => handleItemClick(item)}
                                    title={item.path}
                                  >
                                    <span style={styles.itemName}>{item.name}</span>
                                    {isDirty && <span style={styles.dirtyDot}>●</span>}
                                  </button>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          }

          const filtered = filter
            ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter))
            : state.items
          if (filter && filtered.length === 0) return null

          return (
            <div key={section.label}>
              <button
                style={styles.sectionHeader}
                onClick={() => toggleSection(section.label)}
              >
                <span style={styles.chevron}>{state.open ? '▼' : '▶'}</span>
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
                        style={{
                          ...styles.itemRow,
                          ...(isSelected ? styles.itemRowSelected : {})
                        }}
                        onClick={() => handleItemClick(item)}
                        title={item.path}
                      >
                        <span style={styles.itemName}>{item.name}</span>
                        {isDirty && <span style={styles.dirtyDot}>●</span>}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}

        <div style={styles.divider} />

        <button
          style={{
            ...styles.monitorRow,
            ...(activePanel === 'monitor' ? styles.monitorRowActive : {})
          }}
          onClick={() => setActivePanel('monitor')}
        >
          <span style={styles.monitorDot}>●</span> Monitor
        </button>

        <div style={styles.divider} />
      </div>

      <button
        style={styles.collapseBtn}
        onClick={() => setSidebarCollapsed(true)}
        title="Collapse sidebar"
      >
        ◄
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: '240px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#181825',
    borderRight: '1px solid #313244',
    height: '100%',
    overflow: 'hidden'
  },
  collapsed: {
    width: '32px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: '8px',
    backgroundColor: '#181825',
    borderRight: '1px solid #313244',
    height: '100%'
  },
  expandBtn: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '4px 6px',
    fontSize: '11px'
  },
  filterRow: {
    padding: '8px'
  },
  filterInput: {
    width: '100%',
    boxSizing: 'border-box',
    backgroundColor: '#313244',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    padding: '5px 8px',
    fontSize: '12px',
    outline: 'none'
  },
  treeContainer: {
    flex: 1,
    overflowY: 'auto'
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#a6adc8',
    cursor: 'pointer',
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    textAlign: 'left',
    gap: '4px'
  },
  sectionSub: {
    color: '#6c7086',
    fontWeight: 400,
    textTransform: 'none',
    letterSpacing: 0,
    marginLeft: '4px',
    fontSize: '11px'
  },
  chevron: {
    marginRight: '2px',
    fontSize: '10px',
    flexShrink: 0
  },
  subdirHeader: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#7f849c',
    cursor: 'pointer',
    padding: '4px 12px 4px 24px',
    fontSize: '12px',
    textAlign: 'left',
    gap: '2px'
  },
  convRow: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '3px 12px 3px 24px',
    fontSize: '12px',
    textAlign: 'left'
  },
  convLabel: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },
  convStatus: {
    fontSize: '10px',
    fontWeight: 600,
    flexShrink: 0,
    marginLeft: '6px'
  },
  convEmpty: {
    color: '#6c7086',
    fontSize: '12px',
    padding: '4px 24px',
    fontStyle: 'italic'
  },
  itemRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '4px 12px 4px 28px',
    fontSize: '13px',
    textAlign: 'left'
  },
  itemRowSelected: {
    backgroundColor: '#313244',
    color: '#cba6f7'
  },
  itemName: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },
  dirtyDot: {
    color: '#f38ba8',
    flexShrink: 0,
    marginLeft: '4px',
    fontSize: '10px'
  },
  divider: {
    height: '1px',
    backgroundColor: '#313244',
    margin: '4px 0'
  },
  monitorRow: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    background: 'none',
    border: 'none',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '8px 12px',
    fontSize: '13px',
    textAlign: 'left'
  },
  monitorRowActive: {
    backgroundColor: '#313244',
    color: '#cba6f7'
  },
  monitorDot: {
    color: '#a6e3a1',
    marginRight: '6px'
  },
  collapseBtn: {
    background: 'none',
    border: 'none',
    color: '#6c7086',
    cursor: 'pointer',
    padding: '8px 12px',
    fontSize: '12px',
    textAlign: 'right',
    alignSelf: 'flex-end'
  }
}
