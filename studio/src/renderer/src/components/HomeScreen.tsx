import { useEffect, useState } from 'react'
import { Sun, Moon, LayoutGrid, List, Star, FolderOpen } from 'lucide-react'
import { useStore } from '../store'
import { listDirs, listDir, readFile, pickFolder, openWindow } from '../services/pathlyApi'
import { useTheme } from '../useTheme'
import { Settings } from './Settings'
import type { Theme } from '../theme'
import { isLightPalette } from '../theme'
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

function getCardAccent(plans: PlanRow[], t: Theme): string {
  if (plans.some((p) => p.state.toUpperCase() === 'BLOCKED')) return t.red
  if (plans.some((p) => {
    const s = p.state.toUpperCase()
    return s && s !== 'DONE' && s !== 'IDLE'
  })) return t.accent
  return t.bgSurface1
}

export function HomeScreen(): JSX.Element {
  const { projects, setProjectPath, updateProject, removeProject, addProject, setActiveTopic, setPathlyRoot, theme, setTheme, preferredDark, preferredLight } = useStore()
  const t = useTheme()
  const [projectPlans, setProjectPlans] = useState<ProjectPlans>({})
  const [hideDone, setHideDone] = useState(true)
  const [hoveredPlan, setHoveredPlan] = useState<string | null>(null)
  const [hoveredOpen, setHoveredOpen] = useState<string | null>(null)
  const [hoveredRemove, setHoveredRemove] = useState<string | null>(null)
  const [hoveredCard, setHoveredCard] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(
    (localStorage.getItem('pathly-home-view') as 'grid' | 'list') ?? 'grid'
  )
  const [activeTab, setActiveTab] = useState<'projects' | 'getting-started' | 'settings'>(
    (localStorage.getItem('pathly-home-tab') as 'projects' | 'getting-started' | 'settings') ?? 'projects'
  )
  const INITIAL_VISIBLE = 6
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE)

  function handleTab(tab: 'projects' | 'getting-started' | 'settings'): void {
    localStorage.setItem('pathly-home-tab', tab)
    setActiveTab(tab)
  }

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

  const sorted = [...projects]
    .sort((a, b) => b.lastOpened - a.lastOpened)
    .filter((p, i, arr) => arr.findIndex((x) => x.path === p.path) === i)
  const pinnedProjects = sorted.filter((p) => p.pinned)
  const unpinnedProjects = sorted.filter((p) => !p.pinned)

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

  function renderSectionLabel(label: string, animDelay: number): JSX.Element {
    return (
      <span style={{
        fontSize: '11px',
        fontWeight: 600,
        color: t.textMuted,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        fontFamily: t.fontFamilyBase,
        animation: `fadeIn 350ms ease-out ${animDelay}ms both`
      }}>
        {label}
      </span>
    )
  }

  function renderCard(project: ProjectEntry, idx: number): JSX.Element {
    const allPlans = projectPlans[project.path] ?? []
    const plans = hideDone ? allPlans.filter((p) => p.state.toUpperCase() !== 'DONE') : allPlans
    const isOpenHovered = hoveredOpen === project.path
    const isRemoveHovered = hoveredRemove === project.path
    const isCardHovered = hoveredCard === project.path
    const accentColor = getCardAccent(allPlans, t)

    return (
      <div
        key={project.path}
        style={{
          border: isCardHovered ? `1px solid ${t.accent}50` : `1px solid ${t.bgSurface0}`,
          borderTop: isCardHovered ? `1px solid ${t.accent}50` : `3px solid ${accentColor}`,
          borderRadius: '10px',
          overflow: 'hidden',
          backgroundColor: t.bgMantle,
          boxShadow: isCardHovered ? `0 0 0 1px ${t.accent}20` : 'none',
          transition: 'all 150ms ease-out',
          animation: `fadeSlideUp 300ms ease-out ${80 + idx * 55}ms both`
        }}
        onMouseEnter={() => setHoveredCard(project.path)}
        onMouseLeave={() => setHoveredCard(null)}
      >
        {/* Card header */}
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
            {/* Pin/star button */}
            <button
              aria-label={project.pinned ? 'Unpin project' : 'Pin project'}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '4px',
                borderRadius: '4px',
                opacity: project.pinned ? 1 : (isCardHovered ? 1 : 0),
                transition: 'opacity 150ms',
                color: project.pinned ? '#EAB308' : t.textMuted
              }}
              onClick={(e) => { e.stopPropagation(); updateProject(project.path, { pinned: !project.pinned }) }}
            >
              <Star
                size={12}
                fill={project.pinned ? '#EAB308' : 'none'}
                color={project.pinned ? '#EAB308' : t.textMuted}
              />
            </button>

            {/* Remove button */}
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
                opacity: isCardHovered ? 1 : 0,
                transition: 'all 150ms ease-out, opacity 150ms'
              }}
              onClick={() => removeProject(project.path)}
              onMouseEnter={() => setHoveredRemove(project.path)}
              onMouseLeave={() => setHoveredRemove(null)}
              aria-label={`Remove ${project.name} from list`}
              title="Remove from list"
            >
              <IconClose />
            </button>
          </div>
        </div>

        {/* Topics section */}
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

        {/* Card footer */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          borderTop: `1px solid ${t.bgSurface0}`
        }}>
          <span style={{
            fontSize: '11px',
            color: t.textMuted,
            fontFamily: t.fontFamilyBase
          }}>
            {allPlans.length} topic{allPlans.length !== 1 ? 's' : ''} · {timeAgo(project.lastOpened)}
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
        </div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '56px 24px 64px',
      height: '100vh',
      overflowY: 'auto',
      backgroundColor: t.bgBase,
      color: t.textPrimary,
      fontFamily: t.fontFamilyBase
    }}>
      {/* Combined header — drag region with tabs + dark mode toggle */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '40px',
        background: t.bgMantle,
        borderBottom: `1px solid ${t.bgSurface0}`,
        WebkitAppRegion: 'drag',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        paddingRight: '155px',
        boxSizing: 'border-box',
      } as React.CSSProperties}>
        {/* Tabs — no-drag so clicks register */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          height: '100%',
          WebkitAppRegion: 'no-drag',
        } as React.CSSProperties}>
          {(['projects', 'getting-started', 'settings'] as const).map((tab) => {
            const label = tab === 'projects' ? 'Projects' : tab === 'getting-started' ? 'Getting Started' : 'Settings'
            const isActive = activeTab === tab
            return (
              <button
                key={tab}
                onClick={() => handleTab(tab)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  height: '40px',
                  padding: '0 16px',
                  background: 'none',
                  border: 'none',
                  borderBottom: isActive ? `2px solid ${t.accent}` : '2px solid transparent',
                  color: isActive ? t.textPrimary : t.textMuted,
                  fontSize: '12px',
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: t.fontFamilyBase,
                  cursor: 'pointer',
                  transition: 'color 150ms ease-out, border-color 150ms ease-out',
                  letterSpacing: '0.01em',
                }}
                onMouseEnter={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = t.textSecondary }}
                onMouseLeave={(e) => { if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = t.textMuted }}
              >
                {label}
              </button>
            )
          })}
        </div>
        {/* Dark mode toggle — pushed to right, no-drag */}
        <div style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          WebkitAppRegion: 'no-drag',
        } as React.CSSProperties}>
          <button
            onClick={() => setTheme(isLightPalette(theme) ? preferredDark : preferredLight)}
            title={isLightPalette(theme) ? 'Switch to dark mode' : 'Switch to light mode'}
            aria-label={isLightPalette(theme) ? 'Switch to dark mode' : 'Switch to light mode'}
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
            {isLightPalette(theme) ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        </div>
      </div>

      <style>{ANIMATIONS}</style>

      {activeTab === 'settings' && (
        <div style={{ width: '100%', maxWidth: '1100px' }}>
          <Settings />
        </div>
      )}

      {activeTab === 'getting-started' && (
        <div style={{
          width: '100%',
          maxWidth: '720px',
          animation: 'fadeSlideUp 300ms ease-out both',
        }}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: t.textPrimary, marginBottom: '6px', fontFamily: t.fontFamilyBase }}>
            Getting Started with Pathly Studio
          </h2>
          <p style={{ fontSize: '13px', color: t.textMuted, marginBottom: '28px', fontFamily: t.fontFamilyBase }}>
            A quick overview of how the workspace is structured.
          </p>
          {[
            {
              step: '1',
              title: 'Open a project folder',
              desc: 'Click "+ New project" on the Projects tab and pick a folder that contains a pathly.json or has a pathly/ directory. Pathly will discover all plans and flows inside.',
            },
            {
              step: '2',
              title: 'Create flows in the sidebar',
              desc: 'Once a project is open, use the sidebar to create agent flows (YAML), editor files, or plan boards. The sidebar tree mirrors your project structure.',
            },
            {
              step: '3',
              title: 'Run flows with Monitor',
              desc: 'Select a flow and click Run, or open the Monitor panel (bottom nav) to watch live output and agent logs as your pipeline executes.',
            },
            {
              step: '4',
              title: 'Track work with the Plan Board',
              desc: 'Open any plan folder from the sidebar to see the Kanban-style board. Conversations move from TODO → IN PROGRESS → DONE as you build.',
            },
          ].map(({ step, title, desc }) => (
            <div key={step} style={{
              display: 'flex',
              gap: '16px',
              marginBottom: '20px',
              padding: '16px',
              background: t.bgSurface0,
              borderRadius: '10px',
              border: `1px solid ${t.bgSurface1}`,
            }}>
              <div style={{
                flexShrink: 0,
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: `${t.accent}20`,
                border: `1px solid ${t.accent}40`,
                color: t.accent,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 700,
                fontFamily: t.fontFamilyBase,
              }}>
                {step}
              </div>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: t.textPrimary, marginBottom: '4px', fontFamily: t.fontFamilyBase }}>{title}</div>
                <div style={{ fontSize: '12px', color: t.textMuted, lineHeight: 1.6, fontFamily: t.fontFamilyBase }}>{desc}</div>
              </div>
            </div>
          ))}
          <button
            onClick={() => handleTab('projects')}
            style={{
              marginTop: '8px',
              padding: '8px 20px',
              background: t.accent,
              border: 'none',
              borderRadius: '7px',
              color: '#fff',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: t.fontFamilyBase,
              cursor: 'pointer',
            }}
          >
            Go to Projects →
          </button>
        </div>
      )}

      {activeTab === 'projects' && <>

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
        marginBottom: '32px',
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
          {renderSectionLabel('Recent Projects', 60)}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {/* + New project CTA */}
            <button
              onClick={handleOpenFolder}
              title="Open project folder"
              style={{
                display: 'flex', alignItems: 'center', gap: '5px',
                background: 'none',
                border: `1px solid ${t.accent}`,
                borderRadius: '5px',
                color: t.accent,
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: 500,
                padding: '3px 10px',
                fontFamily: t.fontFamilyBase,
                transition: 'all 150ms ease-out',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = `${t.accent}15` }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'none' }}
            >
              + New project
            </button>
            {/* View toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
              <button
                onClick={() => handleViewMode('grid')}
                title="Grid view"
                aria-label="Grid view"
                aria-pressed={viewMode === 'grid'}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: '26px', height: '26px', borderRadius: '5px', border: 'none',
                  background: viewMode === 'grid' ? `${t.accent}18` : 'none',
                  color: viewMode === 'grid' ? t.accent : t.textMuted,
                  cursor: 'pointer', transition: 'all 150ms ease-out',
                }}
              >
                <LayoutGrid size={13} />
              </button>
              <button
                onClick={() => handleViewMode('list')}
                title="List view"
                aria-label="List view"
                aria-pressed={viewMode === 'list'}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  width: '26px', height: '26px', borderRadius: '5px', border: 'none',
                  background: viewMode === 'list' ? `${t.accent}18` : 'none',
                  color: viewMode === 'list' ? t.accent : t.textMuted,
                  cursor: 'pointer', transition: 'all 150ms ease-out',
                }}
              >
                <List size={13} />
              </button>
            </div>
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
        </div>

        {sorted.length === 0 ? (
          /* Phase 7: Rich empty state */
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: '8px',
            padding: '48px 32px',
            animation: 'fadeSlideUp 300ms ease-out both'
          }}>
            <FolderOpen size={32} color={t.textMuted} />
            <span style={{
              fontSize: '14px',
              fontWeight: 500,
              color: t.textPrimary,
              fontFamily: t.fontFamilyBase
            }}>
              No projects yet
            </span>
            <span style={{
              fontSize: '12px',
              color: t.textMuted,
              fontFamily: t.fontFamilyBase
            }}>
              Open a folder to get started
            </span>
          </div>
        ) : (() => {
          const visiblePinned = pinnedProjects
          const visibleUnpinned = unpinnedProjects.slice(0, Math.max(0, visibleCount - pinnedProjects.length))
          const hiddenCount = unpinnedProjects.length - visibleUnpinned.length
          return (
            <>
              <div style={viewMode === 'grid' ? {
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
                gap: '14px',
              } : {
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                {pinnedProjects.length > 0 && (
                  <>
                    <div style={viewMode === 'grid' ? { gridColumn: '1 / -1' } : {}}>
                      {renderSectionLabel('Pinned', 0)}
                    </div>
                    {visiblePinned.map((project, idx) => renderCard(project, idx))}
                    <div style={{
                      ...(viewMode === 'grid' ? { gridColumn: '1 / -1' } : {}),
                      height: '1px',
                      backgroundColor: t.bgSurface0,
                      margin: '8px 0'
                    }} />
                    <div style={viewMode === 'grid' ? { gridColumn: '1 / -1' } : {}}>
                      {renderSectionLabel('Recent', 0)}
                    </div>
                  </>
                )}
                {(pinnedProjects.length > 0 ? visibleUnpinned : sorted.slice(0, visibleCount))
                  .map((project, idx) => renderCard(project, pinnedProjects.length + idx))}
              </div>

              {hiddenCount > 0 && (
                <button
                  onClick={() => setVisibleCount((n) => n + 6)}
                  style={{
                    marginTop: '8px',
                    alignSelf: 'center',
                    background: 'none',
                    border: `1px solid ${t.bgSurface1}`,
                    borderRadius: '6px',
                    color: t.textMuted,
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontWeight: 500,
                    padding: '6px 18px',
                    fontFamily: t.fontFamilyBase,
                    transition: 'all 150ms ease-out',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = t.accent
                    ;(e.currentTarget as HTMLButtonElement).style.color = t.accent
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = t.bgSurface1
                    ;(e.currentTarget as HTMLButtonElement).style.color = t.textMuted
                  }}
                >
                  Show {hiddenCount} more
                </button>
              )}
            </>
          )
        })()}
      </div>
    </>}
    </div>
  )
}
