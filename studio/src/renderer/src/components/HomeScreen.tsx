import { useEffect, useState } from 'react'
import { Sun, Moon, LayoutGrid, List } from 'lucide-react'
import { useStore } from '../store'
import { listDirs, listDir, readFile, pickFolder, openWindow } from '../services/pathlyApi'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'
import type { ProjectEntry } from '../types'

const ANIMATIONS = `
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes pulseRed {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.55; }
}
@keyframes pulseLive {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}
`

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

function IconArrow(): JSX.Element {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'block' }}>
      <path d="M2.5 7h9M7.5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function IconClose(): JSX.Element {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ display: 'block' }}>
      <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}

function FlowTypeBadge({ flowType, t }: { flowType: 'team' | 'debug' | 'explore'; t: Theme }): JSX.Element {
  const color = flowType === 'team' ? t.accent : flowType === 'debug' ? t.red : t.green
  return (
    <span style={{
      fontSize: '10px',
      fontWeight: 600,
      color,
      border: `1px solid ${color}`,
      borderRadius: '4px',
      padding: '1px 6px',
      opacity: 0.85,
      fontFamily: t.fontFamilyMono,
      flexShrink: 0,
      letterSpacing: '0.04em'
    }}>{flowType}</span>
  )
}

function FsmBadge({ state, t }: { state: string; t: Theme }): JSX.Element {
  const s = state.toUpperCase()

  if (!s || s === 'IDLE') {
    return (
      <span style={{
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        backgroundColor: t.bgSurface1,
        display: 'inline-block',
        flexShrink: 0
      }} title="Idle" />
    )
  }

  if (s === 'DONE') {
    return (
      <span style={{
        color: t.green,
        fontSize: '11px',
        fontWeight: 600,
        fontFamily: t.fontFamilyBase,
        letterSpacing: '0.03em'
      }}>Done</span>
    )
  }

  if (s === 'BLOCKED') {
    return (
      <span style={{
        color: t.red,
        fontSize: '11px',
        fontWeight: 700,
        fontFamily: t.fontFamilyBase,
        letterSpacing: '0.03em',
        animation: 'pulseRed 1.8s ease-in-out infinite'
      }}>Blocked</span>
    )
  }

  if (s === 'BUILDING' || s === 'REVIEWING' || s === 'COMMITTING') {
    return (
      <span style={{
        color: t.blue,
        fontSize: '11px',
        fontWeight: 600,
        fontFamily: t.fontFamilyBase,
        animation: 'pulseLive 2.4s ease-in-out infinite'
      }}>{state.charAt(0).toUpperCase() + state.slice(1).toLowerCase()}</span>
    )
  }

  if (s === 'PLANNING' || s === 'STORMING') {
    return (
      <span style={{
        color: t.accent,
        fontSize: '11px',
        fontWeight: 600,
        fontFamily: t.fontFamilyBase,
        animation: 'pulseLive 2.4s ease-in-out infinite'
      }}>{state.charAt(0).toUpperCase() + state.slice(1).toLowerCase()}</span>
    )
  }

  return (
    <span style={{ color: t.textMuted, fontSize: '11px', fontFamily: t.fontFamilyBase }}>
      {state.charAt(0).toUpperCase() + state.slice(1).toLowerCase()}
    </span>
  )
}

interface PlanRow {
  name: string
  state: string
  flowType: 'team' | 'debug' | 'explore'
}

interface ProjectPlans {
  [projectPath: string]: PlanRow[]
}

export function HomeScreen(): JSX.Element {
  const { projects, setProjectPath, updateProject, removeProject, addProject, setActiveTopic, setPathlyRoot, theme, setTheme } = useStore()
  const t = useTheme()
  const [projectPlans, setProjectPlans] = useState<ProjectPlans>({})
  const [hideDone, setHideDone] = useState(true)
  const [hoveredPlan, setHoveredPlan] = useState<string | null>(null)
  const [hoveredOpen, setHoveredOpen] = useState<string | null>(null)
  const [hoveredRemove, setHoveredRemove] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(
    (localStorage.getItem('pathly-home-view') as 'grid' | 'list') ?? 'grid'
  )

  function handleViewMode(mode: 'grid' | 'list'): void {
    localStorage.setItem('pathly-home-view', mode)
    setViewMode(mode)
  }

  useEffect(() => {
    const ROOTS: Array<{ subdir: string; flowType: 'team' | 'debug' | 'explore' }> = [
      { subdir: 'pathly/plans',        flowType: 'team'    },
      { subdir: 'pathly/debugs',       flowType: 'debug'   },
      { subdir: 'pathly/explorations', flowType: 'explore' },
    ]

    async function scanRoot(
      projectPath: string,
      subdir: string,
      flowType: 'team' | 'debug' | 'explore'
    ): Promise<PlanRow[]> {
      const dir = `${projectPath}/${subdir}`
      const folders = await listDirs(dir).catch(() => [] as string[])
      const rows: PlanRow[] = []
      for (const folder of folders) {
        if (folder === '.archive') continue
        try {
          const raw = await readFile(`${dir}/${folder}/STATE.json`)
          const parsed = JSON.parse(raw) as { current?: string }
          rows.push({ name: folder, state: parsed.current ?? '', flowType })
        } catch {
          rows.push({ name: folder, state: '', flowType })
        }
      }
      return rows
    }

    async function loadAllPlans(): Promise<void> {
      const result: ProjectPlans = {}
      for (const project of projects) {
        try {
          listDir(`${project.path}/src/pathly_data/core/flows`)
            .then(() => setPathlyRoot(project.path))
            .catch(() => { /* not a pathly installation */ })

          const allRows: PlanRow[] = []
          for (const root of ROOTS) {
            const rows = await scanRoot(project.path, root.subdir, root.flowType)
            allRows.push(...rows)
          }
          result[project.path] = allRows
          const active = allRows.find((r) => r.state && r.state !== 'DONE' && r.state !== 'IDLE')
          updateProject(project.path, {
            activeTopic: active?.name ?? allRows[0]?.name,
            fsmState: active?.state ?? allRows[0]?.state ?? ''
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
    const folderPath = await pickFolder()
    if (!folderPath) return
    const name = folderPath.split(/[/\\]/).filter(Boolean).pop() ?? folderPath
    addProject({ path: folderPath, name, lastOpened: Date.now() })
  }

  function handleOpen(project: ProjectEntry, topicName?: string, evt?: React.MouseEvent): void {
    if (evt?.metaKey || evt?.ctrlKey) {
      openWindow(project.path)
    } else {
      updateProject(project.path, { lastOpened: Date.now() })
      if (topicName) setActiveTopic(topicName)
      setProjectPath(project.path)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '48px 24px 64px',
      minHeight: '100vh',
      backgroundColor: t.bgBase,
      color: t.textPrimary,
      fontFamily: t.fontFamilyBase
    }}>
      {/* Drag strip — matches titleBarOverlay color so the top feels seamless */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '36px',
        background: t.bgMantle,
        WebkitAppRegion: 'drag',
        zIndex: 9999,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        paddingRight: '8px',
        boxSizing: 'border-box',
      } as React.CSSProperties}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          WebkitAppRegion: 'no-drag',
          pointerEvents: 'all',
        } as React.CSSProperties}>
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              border: 'none',
              background: 'none',
              color: t.textMuted,
              cursor: 'pointer',
              transition: 'background 150ms ease-out',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = t.bgSurface0 }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <button
            onClick={() => handleViewMode('grid')}
            title="Grid view"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              border: 'none',
              background: 'none',
              color: viewMode === 'grid' ? t.accent : t.textMuted,
              cursor: 'pointer',
              transition: 'background 150ms ease-out',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = t.bgSurface0 }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
          >
            <LayoutGrid size={14} />
          </button>
          <button
            onClick={() => handleViewMode('list')}
            title="List view"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              border: 'none',
              background: 'none',
              color: viewMode === 'list' ? t.accent : t.textMuted,
              cursor: 'pointer',
              transition: 'background 150ms ease-out',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = t.bgSurface0 }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent' }}
          >
            <List size={14} />
          </button>
        </div>
      </div>
      <style>{ANIMATIONS}</style>

      <h1 style={{
        fontSize: '26px',
        fontWeight: 700,
        marginBottom: '8px',
        color: t.accent,
        fontFamily: t.fontFamilyBase,
        letterSpacing: '-0.02em',
        animation: 'fadeIn 400ms ease-out both'
      }}>
        Pathly Studio
      </h1>
      <p style={{
        fontSize: '14px',
        fontWeight: 400,
        color: t.textMuted,
        marginBottom: '36px',
        animation: 'fadeIn 400ms ease-out both'
      }}>
        Welcome back. Pick up where you left off.
      </p>

      <div style={{
        width: '100%',
        maxWidth: '1100px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '4px',
          animation: 'fadeIn 350ms ease-out 60ms both'
        }}>
          <span style={{
            fontSize: '11px',
            fontWeight: 600,
            color: t.textMuted,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            fontFamily: t.fontFamilyBase
          }}>
            Recent Projects
          </span>
          <button
            onClick={() => setHideDone((v) => !v)}
            style={{
              background: 'none',
              border: `1px solid ${hideDone ? t.accent : t.bgSurface1}`,
              borderRadius: '5px',
              color: hideDone ? t.accent : t.textMuted,
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: 500,
              padding: '3px 10px',
              fontFamily: t.fontFamilyBase,
              transition: 'all 150ms ease-out',
              letterSpacing: '0.02em'
            }}
          >
            {hideDone ? 'Show all' : 'Hide done'}
          </button>
        </div>

        <div style={viewMode === 'grid' ? {
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '14px',
        } : {
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>

        {sorted.length === 0 && (
          <div style={{
            padding: '32px 24px',
            textAlign: 'center',
            color: t.textMuted,
            border: `1px solid ${t.bgSurface0}`,
            borderRadius: '10px',
            fontSize: '13px',
            fontFamily: t.fontFamilyBase,
            animation: 'fadeSlideUp 300ms ease-out both'
          }}>
            No projects yet. Open a folder to get started.
          </div>
        )}

        {sorted.map((project, idx) => {
          const allPlans = projectPlans[project.path] ?? []
          const plans = hideDone ? allPlans.filter((p) => p.state.toUpperCase() !== 'DONE') : allPlans
          const isOpenHovered = hoveredOpen === project.path
          const isRemoveHovered = hoveredRemove === project.path

          return (
            <div
              key={project.path}
              style={{
                border: `1px solid ${t.bgSurface0}`,
                borderRadius: '10px',
                overflow: 'hidden',
                backgroundColor: t.bgMantle,
                animation: `fadeSlideUp 300ms ease-out ${80 + idx * 55}ms both`
              }}
            >
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderBottom: plans.length > 0 ? `1px solid ${t.bgSurface0}` : 'none',
                backgroundColor: t.bgBase
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', minWidth: 0 }}>
                  <span style={{
                    fontWeight: 600,
                    fontSize: '14px',
                    color: t.textPrimary,
                    flexShrink: 0,
                    fontFamily: t.fontFamilyBase
                  }}>
                    {project.name}
                  </span>
                  <span style={{
                    fontSize: '11px',
                    color: t.textMuted,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontFamily: t.fontFamilyMono
                  }}>
                    {project.path}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                  <span style={{ fontSize: '11px', color: t.textMuted, fontFamily: t.fontFamilyBase }}>
                    {timeAgo(project.lastOpened)}
                  </span>

                  <button
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: isOpenHovered ? `${t.accent}18` : 'none',
                      border: `1px solid ${isOpenHovered ? t.accent : t.bgSurface1}`,
                      borderRadius: '6px',
                      color: isOpenHovered ? t.accent : t.textSecondary,
                      cursor: 'pointer',
                      padding: '4px 10px',
                      fontSize: '12px',
                      fontWeight: 500,
                      fontFamily: t.fontFamilyBase,
                      transition: 'all 150ms ease-out'
                    }}
                    onClick={(e) => handleOpen(project, undefined, e)}
                    onMouseEnter={() => setHoveredOpen(project.path)}
                    onMouseLeave={() => setHoveredOpen(null)}
                    title="Open project"
                  >
                    <IconArrow />
                    Open
                  </button>

                  <button
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: isRemoveHovered ? `${t.red}15` : 'none',
                      border: `1px solid ${isRemoveHovered ? t.red : t.bgSurface0}`,
                      borderRadius: '6px',
                      color: isRemoveHovered ? t.red : t.textMuted,
                      cursor: 'pointer',
                      width: '28px',
                      height: '28px',
                      padding: 0,
                      transition: 'all 150ms ease-out'
                    }}
                    onClick={() => removeProject(project.path)}
                    onMouseEnter={() => setHoveredRemove(project.path)}
                    onMouseLeave={() => setHoveredRemove(null)}
                    title="Remove from list"
                  >
                    <IconClose />
                  </button>
                </div>
              </div>

              {plans.length === 0 ? (
                <div style={{
                  padding: '10px 16px',
                  fontSize: '12px',
                  color: t.textMuted,
                  fontStyle: 'italic',
                  fontFamily: t.fontFamilyBase
                }}>
                  No active topics
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {plans.map((plan) => {
                    const key = `${plan.flowType}:${plan.name}`
                    const isHovered = hoveredPlan === key
                    const isBlocked = plan.state.toUpperCase() === 'BLOCKED'

                    return (
                      <div
                        key={key}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '7px 16px 7px 20px',
                          borderBottom: `1px solid ${t.bgBase}`,
                          borderLeft: `3px solid ${isBlocked ? t.red : isHovered ? t.accent : 'transparent'}`,
                          cursor: 'pointer',
                          backgroundColor: isHovered ? t.bgSurface0 : 'transparent',
                          transition: 'all 150ms ease-out'
                        }}
                        onClick={(e) => handleOpen(project, plan.name, e)}
                        title={`Open ${plan.name}`}
                        onMouseEnter={() => setHoveredPlan(key)}
                        onMouseLeave={() => setHoveredPlan(null)}
                      >
                        <span style={{
                          fontSize: '12px',
                          color: isBlocked ? `${t.red}CC` : t.textSecondary,
                          fontFamily: t.fontFamilyMono,
                          transition: 'color 150ms ease-out'
                        }}>
                          {plan.name}
                        </span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <FlowTypeBadge flowType={plan.flowType} t={t} />
                          <FsmBadge state={plan.state} t={t} />
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
        </div>
      </div>

      <button
        style={{
          marginTop: '28px',
          padding: '9px 22px',
          background: 'none',
          border: `1px solid ${t.accent}`,
          borderRadius: '8px',
          color: t.accent,
          cursor: 'pointer',
          fontSize: '13px',
          fontWeight: 500,
          fontFamily: t.fontFamilyBase,
          transition: 'all 150ms ease-out',
          letterSpacing: '0.01em',
          animation: `fadeIn 350ms ease-out ${80 + sorted.length * 55 + 60}ms both`
        }}
        onClick={handleOpenFolder}
        onMouseEnter={(e) => {
          const el = e.currentTarget
          el.style.background = `${t.accent}15`
          el.style.boxShadow = `0 0 16px ${t.accent}30`
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget
          el.style.background = 'none'
          el.style.boxShadow = 'none'
        }}
      >
        + Open project folder
      </button>
    </div>
  )
}
