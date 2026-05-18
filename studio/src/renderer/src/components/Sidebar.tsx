import { useState } from 'react'
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

const SECTIONS: Section[] = [
  { label: 'Flows',        type: 'flow',     dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',       type: 'skill',    dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',       type: 'agent',    dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates',    type: 'template', dir: 'src/pathly_data/core/templates' },
  { label: 'Debugs',       type: 'debug',    dir: 'pathly/debugs'                  },
  { label: 'Explorations', type: 'explore',  dir: 'pathly/explorations'            },
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

          if (section.type === 'template' || section.type === 'debug' || section.type === 'explore') {
            if (state.subdirs === null) return null
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
                      <button className={styles.newBtn} onClick={() => handleNewItem(section)}>
                        {section.type === 'template' ? '+ new template' : section.type === 'explore' ? '+ new exploration' : '+ new debug'}
                      </button>
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
    </div>
  )
}
