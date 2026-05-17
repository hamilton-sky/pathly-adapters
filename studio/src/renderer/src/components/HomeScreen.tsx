import { useEffect } from 'react'
import { useStore } from '../store'
import type { ProjectEntry } from '../types'

function timeAgo(ts: number): string {
  const diffMs = Date.now() - ts
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hr ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`
}

function FsmBadge({ state }: { state: string | undefined }): JSX.Element {
  if (!state) return <span style={{ color: '#6c7086' }}>— nothing in progress</span>
  const s = state.toUpperCase()
  if (s === 'BUILDING') return <span style={{ color: '#4a9eff' }}>● BUILDING</span>
  if (s === 'DONE') return <span style={{ color: '#4caf50' }}>✓ DONE</span>
  if (s === 'BLOCKED') return <span style={{ color: '#f44336' }}>● BLOCKED</span>
  return <span style={{ color: '#a6adc8' }}>● {state}</span>
}

export function HomeScreen(): JSX.Element {
  const { projects, setProjectPath, updateProject, removeProject, addProject } = useStore()

  useEffect(() => {
    async function loadProjectStates(): Promise<void> {
      for (const project of projects) {
        try {
          const plansDir = `${project.path}/pathly/plans/`
          const topics = await window.pathly.fs.list(plansDir)
          if (topics.length === 0) continue

          for (const topic of topics) {
            try {
              const stateRaw = await window.pathly.fs.read(
                `${plansDir}${topic}/STATE.json`
              )
              if (stateRaw) {
                const parsed = JSON.parse(stateRaw) as { state?: string }
                updateProject(project.path, {
                  activeTopic: topic,
                  fsmState: parsed.state ?? ''
                })
                break
              }
            } catch {
              // topic has no STATE.json — skip
            }
          }
        } catch {
          // project has no plans dir — ignore
        }
      }
    }

    loadProjectStates()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = [...projects].sort((a, b) => b.lastOpened - a.lastOpened)

  async function handleOpenFolder(): Promise<void> {
    const folderPath = await window.pathly.fs.pickFolder()
    if (!folderPath) return
    const name = folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath
    addProject({ path: folderPath, name, lastOpened: Date.now() })
  }

  function handleOpen(project: ProjectEntry, evt: React.MouseEvent): void {
    if (evt.metaKey || evt.ctrlKey) {
      window.pathly.shell.openWindow(project.path)
    } else {
      updateProject(project.path, { lastOpened: Date.now() })
      setProjectPath(project.path)
    }
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Pathly Studio</h1>

      <div style={styles.section}>
        <div style={styles.sectionLabel}>Recent projects</div>
        <div style={styles.projectList}>
          {sorted.length === 0 && (
            <div style={styles.emptyState}>
              No projects yet. Open a project folder to get started.
            </div>
          )}
          {sorted.map((project) => (
            <div key={project.path} style={styles.projectRow}>
              <div style={styles.projectTop}>
                <span style={styles.projectName}>{project.name}</span>
                <span style={styles.projectPath}>{project.path}</span>
              </div>
              <div style={styles.projectBottom}>
                <span style={styles.fsmBadge}>
                  <FsmBadge state={project.fsmState} />
                  {project.activeTopic && project.fsmState && (
                    <span style={styles.topicLabel}>  {project.activeTopic}</span>
                  )}
                </span>
                <span style={styles.timeAgo}>{timeAgo(project.lastOpened)}</span>
                <button
                  style={styles.openBtn}
                  onClick={(e) => handleOpen(project, e)}
                  title="Open project (Cmd/Ctrl+click to open in new window)"
                >
                  →
                </button>
                <button
                  style={styles.removeBtn}
                  onClick={() => removeProject(project.path)}
                  title="Remove from list"
                >
                  ×
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <button style={styles.openFolderBtn} onClick={handleOpenFolder}>
        + Open project folder
      </button>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '40px 24px',
    minHeight: '100vh',
    backgroundColor: '#1e1e2e',
    color: '#cdd6f4',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  },
  title: {
    fontSize: '28px',
    fontWeight: 600,
    marginBottom: '32px',
    color: '#cba6f7'
  },
  section: {
    width: '100%',
    maxWidth: '760px',
    marginBottom: '24px'
  },
  sectionLabel: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#a6adc8',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  },
  projectList: {
    border: '1px solid #313244',
    borderRadius: '8px',
    overflow: 'hidden'
  },
  emptyState: {
    padding: '24px',
    textAlign: 'center',
    color: '#6c7086'
  },
  projectRow: {
    padding: '14px 16px',
    borderBottom: '1px solid #313244',
    backgroundColor: '#181825'
  },
  projectTop: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '16px',
    marginBottom: '6px'
  },
  projectName: {
    fontWeight: 600,
    fontSize: '15px',
    color: '#cdd6f4',
    flexShrink: 0
  },
  projectPath: {
    fontSize: '12px',
    color: '#6c7086',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },
  projectBottom: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px'
  },
  fsmBadge: {
    fontSize: '13px',
    flex: 1
  },
  topicLabel: {
    color: '#a6adc8',
    fontSize: '12px'
  },
  timeAgo: {
    fontSize: '12px',
    color: '#6c7086',
    flexShrink: 0
  },
  openBtn: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#cdd6f4',
    cursor: 'pointer',
    padding: '2px 10px',
    fontSize: '14px',
    flexShrink: 0
  },
  removeBtn: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#6c7086',
    cursor: 'pointer',
    padding: '2px 8px',
    fontSize: '14px',
    flexShrink: 0
  },
  openFolderBtn: {
    marginTop: '8px',
    padding: '8px 18px',
    background: 'none',
    border: '1px solid #cba6f7',
    borderRadius: '6px',
    color: '#cba6f7',
    cursor: 'pointer',
    fontSize: '14px'
  }
}
