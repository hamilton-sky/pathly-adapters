import { useEffect, useState } from 'react'
import { useStore } from '../store'
import type { PathlyItem, PathlyItemType } from '../types'

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

interface SectionState {
  items: PathlyItem[]
  open: boolean
}

export function Sidebar(): JSX.Element {
  const {
    projectPath,
    sidebarCollapsed,
    setSidebarCollapsed,
    selectedItem,
    setSelectedItem,
    setActivePanel,
    dirtyItems,
    activePanel
  } = useStore()

  const [sections, setSections] = useState<Record<string, SectionState>>({
    Flows: { items: [], open: true },
    Skills: { items: [], open: false },
    Agents: { items: [], open: false },
    Templates: { items: [], open: false }
  })
  const [filter, setFilter] = useState('')

  useEffect(() => {
    if (!projectPath) return

    async function loadItems(): Promise<void> {
      const updates: Record<string, PathlyItem[]> = {}

      for (const section of SECTIONS) {
        try {
          const dir = `${projectPath}/${section.dir}`
          const names = await window.pathly.fs.list(dir)
          updates[section.label] = names.map((name) => ({
            name,
            path: `${dir}/${name}`,
            type: section.type
          }))
        } catch {
          updates[section.label] = []
        }
      }

      setSections((prev) => {
        const next = { ...prev }
        for (const [label, items] of Object.entries(updates)) {
          next[label] = { ...next[label], items }
        }
        return next
      })
    }

    loadItems()
  }, [projectPath])

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
        {SECTIONS.map((section) => {
          const state = sections[section.label]
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
                {section.label}
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
    textAlign: 'left'
  },
  chevron: {
    marginRight: '6px',
    fontSize: '10px'
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
