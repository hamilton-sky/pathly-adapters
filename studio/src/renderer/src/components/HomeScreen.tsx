import { useEffect, useState } from 'react'
import { useStore } from '../store'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'
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
  return `${diffDay}d ago`
}

function FsmBadge({ state, t }: { state: string; t: Theme }): JSX.Element {
  const s = state.toUpperCase()
  if (!s || s === 'IDLE') return <span style={{ color: t.textMuted, fontSize: '12px' }}>—</span>
  if (s === 'DONE') return <span style={{ color: t.green, fontSize: '12px', fontWeight: 600 }}>✓ DONE</span>
  if (s === 'BUILDING' || s === 'REVIEWING' || s === 'COMMITTING')
    return <span style={{ color: t.blue, fontSize: '12px', fontWeight: 600 }}>● {state}</span>
  if (s === 'BLOCKED') return <span style={{ color: t.red, fontSize: '12px', fontWeight: 600 }}>● BLOCKED</span>
  if (s === 'PLANNING' || s === 'STORMING')
    return <span style={{ color: t.accent, fontSize: '12px', fontWeight: 600 }}>● {state}</span>
  return <span style={{ color: t.textMuted, fontSize: '12px' }}>● {state}</span>
}

interface PlanRow {
  name: string
  state: string
}

interface ProjectPlans {
  [projectPath: string]: PlanRow[]
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '40px 24px',
      minHeight: '100vh',
      backgroundColor: t.bgBase,
      color: t.textPrimary,
      fontFamily: 'system-ui, -apple-system, sans-serif'
    },
    title: {
      fontSize: '28px',
      fontWeight: 600,
      marginBottom: '32px',
      color: t.accent
    },
    section: {
      width: '100%',
      maxWidth: '820px',
      marginBottom: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    },
    sectionLabel: {
      fontSize: '13px',
      fontWeight: 600,
      color: t.textSecondary,
      marginBottom: '4px',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em'
    },
    emptyState: {
      padding: '24px',
      textAlign: 'center' as const,
      color: t.textMuted,
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '8px'
    },
    projectCard: {
      border: `1px solid ${t.bgSurface0}`,
      borderRadius: '8px',
      overflow: 'hidden',
      backgroundColor: t.bgMantle
    },
    projectHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '12px 16px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      backgroundColor: t.bgBase
    },
    projectMeta: {
      display: 'flex',
      alignItems: 'baseline',
      gap: '12px',
      minWidth: 0
    },
    projectName: {
      fontWeight: 700,
      fontSize: '15px',
      color: t.textPrimary,
      flexShrink: 0
    },
    projectPath: {
      fontSize: '12px',
      color: t.textMuted,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap' as const
    },
    projectActions: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      flexShrink: 0
    },
    timeAgo: {
      fontSize: '12px',
      color: t.textMuted
    },
    openBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textPrimary,
      cursor: 'pointer',
      padding: '2px 10px',
      fontSize: '14px'
    },
    removeBtn: {
      background: 'none',
      border: `1px solid ${t.bgSurface1}`,
      borderRadius: '4px',
      color: t.textMuted,
      cursor: 'pointer',
      padding: '2px 8px',
      fontSize: '14px'
    },
    noPlans: {
      padding: '10px 16px',
      fontSize: '12px',
      color: t.textMuted,
      fontStyle: 'italic'
    },
    planTable: {
      display: 'flex',
      flexDirection: 'column' as const
    },
    planRow: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '8px 16px 8px 24px',
      borderBottom: `1px solid ${t.bgBase}`,
      cursor: 'pointer',
      transition: 'background 0.1s'
    },
    planName: {
      fontSize: '13px',
      color: t.textSecondary,
      fontFamily: 'monospace'
    },
    openFolderBtn: {
      marginTop: '8px',
      padding: '8px 18px',
      background: 'none',
      border: `1px solid ${t.accent}`,
      borderRadius: '6px',
      color: t.accent,
      cursor: 'pointer',
      fontSize: '14px'
    }
  }
}

export function HomeScreen(): JSX.Element {
  const { projects, setProjectPath, updateProject, removeProject, addProject, setActiveTopic } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)
  const [projectPlans, setProjectPlans] = useState<ProjectPlans>({})

  useEffect(() => {
    async function loadAllPlans(): Promise<void> {
      const result: ProjectPlans = {}
      for (const project of projects) {
        try {
          const plansDir = `${project.path}/pathly/plans`
          const planFolders = await window.pathly.fs.listDirs(plansDir)
          const rows: PlanRow[] = []
          for (const folder of planFolders) {
            if (folder === '.archive') continue
            try {
              const raw = await window.pathly.fs.read(`${plansDir}/${folder}/STATE.json`)
              const parsed = JSON.parse(raw) as { current?: string }
              rows.push({ name: folder, state: parsed.current ?? '' })
            } catch {
              rows.push({ name: folder, state: '' })
            }
          }
          result[project.path] = rows
          const active = rows.find((r) => r.state && r.state !== 'DONE' && r.state !== 'IDLE')
          updateProject(project.path, {
            activeTopic: active?.name ?? rows[0]?.name,
            fsmState: active?.state ?? rows[0]?.state ?? ''
          })
        } catch {
          result[project.path] = []
        }
      }
      setProjectPlans(result)
    }
    loadAllPlans()
  }, [projects.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = [...projects].sort((a, b) => b.lastOpened - a.lastOpened)

  async function handleOpenFolder(): Promise<void> {
    const folderPath = await window.pathly.fs.pickFolder()
    if (!folderPath) return
    const name = folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath
    addProject({ path: folderPath, name, lastOpened: Date.now() })
  }

  function handleOpen(project: ProjectEntry, topicName?: string, evt?: React.MouseEvent): void {
    if (evt?.metaKey || evt?.ctrlKey) {
      window.pathly.shell.openWindow(project.path)
    } else {
      updateProject(project.path, { lastOpened: Date.now() })
      if (topicName) setActiveTopic(topicName)
      setProjectPath(project.path)
    }
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Pathly Studio</h1>

      <div style={styles.section}>
        <div style={styles.sectionLabel}>Recent projects</div>

        {sorted.length === 0 && (
          <div style={styles.emptyState}>
            No projects yet. Open a project folder to get started.
          </div>
        )}

        {sorted.map((project) => {
          const plans = projectPlans[project.path] ?? []
          return (
            <div key={project.path} style={styles.projectCard}>
              <div style={styles.projectHeader}>
                <div style={styles.projectMeta}>
                  <span style={styles.projectName}>{project.name}</span>
                  <span style={styles.projectPath}>{project.path}</span>
                </div>
                <div style={styles.projectActions}>
                  <span style={styles.timeAgo}>{timeAgo(project.lastOpened)}</span>
                  <button
                    style={styles.openBtn}
                    onClick={(e) => handleOpen(project, undefined, e)}
                    title="Open project"
                  >→</button>
                  <button
                    style={styles.removeBtn}
                    onClick={() => removeProject(project.path)}
                    title="Remove from list"
                  >×</button>
                </div>
              </div>

              {plans.length === 0 ? (
                <div style={styles.noPlans}>No plans found in pathly/plans/</div>
              ) : (
                <div style={styles.planTable}>
                  {plans.map((plan) => (
                    <div
                      key={plan.name}
                      style={styles.planRow}
                      onClick={(e) => handleOpen(project, plan.name, e)}
                      title={`Open ${plan.name}`}
                    >
                      <span style={styles.planName}>{plan.name}</span>
                      <FsmBadge state={plan.state} t={t} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <button style={styles.openFolderBtn} onClick={handleOpenFolder}>
        + Open project folder
      </button>
    </div>
  )
}
