import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import { HealthCheck } from './HealthCheck'
import { Tooltip } from '../ui/Tooltip'
import type { FsmEvent } from '../../types/index'
import { watchStart, readFile, onWatchEvent } from '../../services/pathlyApi'
import { useInjectCSS, useAgentTelemetry } from './utils'

type FlowType = 'team' | 'debug' | 'explore'

function getFlowYamlName(flow: string | undefined): string {
  switch (flow as FlowType) {
    case 'team': return 'team.flow.yaml'
    case 'debug': return 'debug.flow.yaml'
    case 'explore': return 'explore.flow.yaml'
    default:
      if (flow !== undefined) {
        console.warn(`[Monitor] Unknown flow type "${flow}", falling back to team.flow.yaml`)
      }
      return 'team.flow.yaml'
  }
}

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '…' : s
}

// Session keys are "flowType/topic" (e.g. "debug/security-hardening").
// extractTopic strips the flow-type prefix; safe on plain topic strings too.
function extractTopic(sessionKey: string): string {
  const slash = sessionKey.indexOf('/')
  return slash === -1 ? sessionKey : sessionKey.slice(slash + 1)
}

function flowTypeLabel(flowKey: string): string {
  const t = flowKey.replace('.flow.yaml', '')
  return t === 'team' ? 'plan' : t
}

const LIVE_BADGE_CSS = `
@keyframes pathly-live-breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.pathly-live-dot {
  animation: none;
}
@media (prefers-reduced-motion: no-preference) {
  .pathly-live-dot { animation: pathly-live-breathe 2s ease-in-out infinite; }
}
`

const EMPTY_TOOLTIP = 'Waiting for AGENT_DONE events with telemetry'

function fmtTokens(n: number): string {
  if (n === 0) return '—'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}
function fmtWall(n: number | undefined): string {
  return n == null ? '—' : `${n}s`
}
function fmtCost(n: number): string {
  return n === 0 ? '—' : `$${n.toFixed(2)}`
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    panel: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      overflow: 'auto'
    },
    placeholder: {
      margin: 'auto',
      color: t.textMuted,
      fontSize: '15px'
    },
    header: {
      backgroundColor: t.bgSurface0,
      borderBottom: `1px solid ${t.bgSurface1}`,
      padding: '8px 12px',
      flexShrink: 0,
      fontFamily: 'system-ui, -apple-system, sans-serif',
      fontSize: '13px',
      lineHeight: '1.6',
      color: t.textSecondary
    },
    headerTitle: {
      color: t.accent,
      fontWeight: 600,
      marginBottom: '2px'
    },
    headerRow: {
      display: 'flex',
      gap: '24px'
    },
    tabBar: {
      height: '32px',
      display: 'flex',
      alignItems: 'center',
      borderBottom: `1px solid ${t.bgSurface0}`,
      backgroundColor: t.bgMantle,
      paddingLeft: '8px',
      gap: '2px',
      flexShrink: 0
    }
  }
}

function HeaderBar({ effectiveTopic }: { effectiveTopic: string | null }): JSX.Element {
  const { fsmState, monitorSource } = useStore()
  const t = useTheme()

  useInjectCSS(LIVE_BADGE_CSS)

  const flow = fsmState?.flow as string | undefined
  const topic = fsmState?.feature
    ? truncate(fsmState.feature as string, 32)
    : effectiveTopic ? truncate(effectiveTopic, 32) : '—'
  const conv = fsmState?.conv != null
    ? String(fsmState.conv)
    : fsmState?.current_conversation != null
      ? String(fsmState.current_conversation)
      : null

  // Meta row: "team · conv 1" — only include known values
  const metaParts: string[] = []
  if (flow) metaParts.push(flow)
  if (conv) metaParts.push(`conv ${conv}`)

  // Connection badge: ● live (green) / ● syncing (amber) / ○ offline (red)
  const badgeDotClass = monitorSource === 'sse' ? 'pathly-live-dot' : undefined
  const badgeDot = monitorSource == null ? '○' : '●'
  const badgeLabel = monitorSource === 'sse' ? 'live'
    : monitorSource === 'chokidar' ? 'syncing' : 'offline'
  const badgeColor = monitorSource === 'sse' ? '#22C55E'
    : monitorSource === 'chokidar' ? '#F59E0B'
    : '#EF4444'
  const badgeAriaLabel = monitorSource === 'sse' ? 'Live SSE connection'
    : monitorSource === 'chokidar' ? 'Syncing via file watcher' : 'Not connected'

  return (
    <div style={{
      backgroundColor: t.bgSurface0,
      borderBottom: `1px solid ${t.bgSurface1}`,
      padding: '8px 12px 6px',
      flexShrink: 0,
    }}>
      {/* Row 1: feature name (bold, large) + connection badge */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{
          fontSize: '14px',
          fontWeight: 600,
          color: t.textPrimary,
          fontFamily: 'system-ui, -apple-system, sans-serif',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {topic}
        </span>
        <span
          role="status"
          aria-live="polite"
          aria-atomic={true}
          aria-label={badgeAriaLabel}
          style={{
            flexShrink: 0,
            marginLeft: '12px',
            fontSize: '11px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            color: badgeColor,
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
          }}
        >
          <span className={badgeDotClass} aria-hidden="true" style={{ color: badgeColor }}>{badgeDot}</span>
          <span aria-hidden="true">{badgeLabel}</span>
        </span>
      </div>
      {/* Row 2: flow · conv — omit entirely if nothing to show */}
      {metaParts.length > 0 && (
        <div style={{
          fontSize: '11px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          color: '#64748B',
          letterSpacing: '0.01em',
        }}>
          {metaParts.join(' · ')}
        </div>
      )}
    </div>
  )
}

interface TabBarProps {
  sessions: Record<string, import('../../types/index').FlowSession>
  activeTab: string | null
  onTabSelect: (topic: string) => void
}

function TabBar({ sessions, activeTab, onTabSelect }: TabBarProps): JSX.Element {
  const t = useTheme()
  const styles = makeStyles(t)
  const keys = Object.keys(sessions)
  const focusedTabRef = useRef<number>(keys.indexOf(activeTab ?? keys[0]))

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLButtonElement>, idx: number): void => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      const nextIdx = (idx + 1) % keys.length
      onTabSelect(keys[nextIdx])
      focusedTabRef.current = nextIdx
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      const prevIdx = (idx - 1 + keys.length) % keys.length
      onTabSelect(keys[prevIdx])
      focusedTabRef.current = prevIdx
    }
  }, [keys, onTabSelect])

  const visible = keys.slice(0, 4)
  const overflow = keys.slice(4)

  // When all sessions share the same topic, just show the flow type (e.g. "plan", "debug").
  // When topics differ, show "flowType/topic" so the user knows which is which.
  const allSameTopic = keys.length > 0 && keys.every(k => extractTopic(k) === extractTopic(keys[0]))

  return (
    <div
      role="tablist"
      aria-label="Active flows"
      style={styles.tabBar}
    >
      {visible.map((sessionKey, idx) => {
        const session = sessions[sessionKey]
        const isActive = activeTab === sessionKey || (activeTab === null && idx === 0)
        const label = allSameTopic
          ? flowTypeLabel(session.flowKey)
          : `${flowTypeLabel(session.flowKey)}/${truncate(extractTopic(sessionKey), 10)}`
        return (
          <button
            key={sessionKey}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onTabSelect(sessionKey)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            style={{
              height: '100%',
              padding: '0 12px',
              fontSize: '12px',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              color: isActive ? t.textPrimary : t.textMuted,
              border: 'none',
              borderBottom: isActive ? `2px solid ${t.runtime}` : '2px solid transparent',
              backgroundColor: isActive ? t.bgSurface0 : 'transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              outline: 'none'
            }}
          >
            {label}
            {session.isRunning && (
              <span
                className="pathly-pulse"
                style={{ color: t.runtime, fontSize: '8px' }}
                aria-hidden="true"
              >●</span>
            )}
          </button>
        )
      })}
      {overflow.length > 0 && (
        <button
          style={{
            height: '100%',
            padding: '0 10px',
            fontSize: '12px',
            color: t.textMuted,
            border: 'none',
            backgroundColor: 'transparent',
            cursor: 'pointer'
          }}
          onClick={() => { /* overflow dropdown — Post-MVP */ }}
        >
          …
        </button>
      )}
    </div>
  )
}

function MetricsStrip(): JSX.Element {
  const t = useTheme()
  const { totalTokens, lastWall, totalCost, noTelemetry, eventsCount } = useAgentTelemetry()

  const tiles: { label: string; value: string; empty: boolean; tooltip?: string }[] = [
    { label: 'TOKENS', value: fmtTokens(totalTokens), empty: totalTokens === 0, tooltip: EMPTY_TOOLTIP },
    { label: 'WALL',   value: fmtWall(lastWall),      empty: lastWall == null,  tooltip: EMPTY_TOOLTIP },
    { label: 'COST',   value: fmtCost(totalCost),     empty: totalCost === 0,   tooltip: EMPTY_TOOLTIP },
    { label: 'EVENTS', value: String(eventsCount),    empty: false },
  ]

  return (
    <div style={{ flexShrink: 0, borderBottom: `1px solid ${t.bgSurface0}` }}>
      <div style={{ display: 'flex' }}>
        {tiles.map((tile, i) => (
          <Tooltip
            key={tile.label}
            label={tile.empty && tile.tooltip ? tile.tooltip : tile.label}
            placement="top"
            delay={300}
          >
          <div
            style={{
              flex: 1,
              height: '44px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              borderLeft: i > 0 ? `1px solid ${t.bgSurface0}` : undefined,
            }}
          >
            <span style={{
              fontSize: '16px',
              fontFamily: t.fontFamilyMono,
              fontWeight: 600,
              // Empty values use deeply muted color so they read as "no data", not "zero"
              color: tile.empty ? '#374151' : t.textPrimary,
              lineHeight: 1,
            }}>
              {tile.value}
            </span>
            <span style={{
              fontSize: '9px',
              color: t.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              marginTop: '3px',
              fontFamily: "'Inter', system-ui, sans-serif",
            }}>
              {tile.label}
            </span>
          </div>
          </Tooltip>
        ))}
      </div>
      {noTelemetry && (
        <div style={{
          fontSize: '10px',
          color: '#4B5563',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontStyle: 'italic',
          padding: '3px 12px 4px',
          borderTop: `1px solid ${t.bgSurface0}`,
        }}>
          No telemetry captured — HTTP pipeline events do not include cost data
        </div>
      )}
    </div>
  )
}

export function Monitor(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    events,
    monitorSource,
    setMonitorSource,
    setFsmState,
    setEvents,
    setPipelineStates,
    activeFlowSessions,
    activeMonitorTab,
    setActiveFlowSessions,
    setActiveMonitorTab
  } = useStore()

  const eventsRef = useRef(events)
  eventsRef.current = events

  const monitorSourceRef = useRef(monitorSource)
  monitorSourceRef.current = monitorSource

  const t = useTheme()
  const styles = makeStyles(t)

  // Session keys are compound "flowType/topic". Extract the plain topic for SSE/file paths.
  const activeTabValid = activeMonitorTab != null && !!activeFlowSessions[activeMonitorTab]
  const effectiveTopic = activeTabValid ? extractTopic(activeMonitorTab!) : activeTopic

  // When the sidebar topic changes, clear all sessions and reset the active tab.
  const prevTopicRef = useRef(activeTopic)
  useEffect(() => {
    if (prevTopicRef.current === activeTopic) return
    prevTopicRef.current = activeTopic
    setActiveFlowSessions(() => ({}))
    setActiveMonitorTab(null)
  }, [activeTopic, setActiveFlowSessions, setActiveMonitorTab])

  useEffect(() => {
    if (!effectiveTopic) {
      setPipelineStates([])
      return
    }

    if (!projectPath) {
      setMonitorSource('chokidar')
      return
    }

    // Probe all three roots in parallel — use whichever has STATE.json.
    const roots = [
      `${projectPath}/pathly/plans/${effectiveTopic}`,
      `${projectPath}/pathly/debugs/${effectiveTopic}`,
      `${projectPath}/pathly/explorations/${effectiveTopic}`,
    ]

    Promise.any(
      roots.map((r) => readFile(`${r}/STATE.json`).then((c) => ({ base: r, content: c })))
    ).then(({ base, content }) => {
      if (!content) return
      try {
        const parsedState = JSON.parse(content)
        if (!parsedState.flow) {
          if (base.includes('/pathly/debugs/')) parsedState.flow = 'debug'
          else if (base.includes('/pathly/explorations/')) parsedState.flow = 'explore'
          else parsedState.flow = 'team'
        }
        if (!parsedState.feature && effectiveTopic) {
          parsedState.feature = effectiveTopic
        }
        setFsmState(parsedState)

        // Upsert session using compound key "flowType/topic" to allow plan + debug in parallel.
        if (activeTopic) {
          const flowType = (parsedState.flow as string | undefined) ?? 'team'
          const sessionKey = `${flowType}/${activeTopic}`
          setActiveFlowSessions((prev) => ({
            ...prev,
            [sessionKey]: {
              flowKey: `${flowType}.flow.yaml`,
              topic: activeTopic,
              isRunning: parsedState.current !== 'IDLE' && parsedState.current !== 'DONE',
              isPaused: false,
              isCli: false as const
            }
          }))
        }

        const flowName = parsedState.flow as string | undefined
        if (!flowName) return
        const yamlName = getFlowYamlName(flowName)
        readFile(`${projectPath}/src/pathly_data/core/flows/${yamlName}`)
          .then((yaml) => {
            const cleanYaml = yaml.replace(/\r/g, '')
            const match = cleanYaml.match(/states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/)
            if (match) {
              const states = match[1]
                .trim()
                .split('\n')
                .map((l) => l.replace(/^[ \t]+-[ \t]+/, '').trim().toUpperCase())
                .filter(Boolean)
              setPipelineStates(states)
            }
          })
          .catch(() => { /* flow YAML missing — FsmView uses fallback */ })

        // Load events from the correct base path
        readFile(`${base}/EVENTS.jsonl`).then((evContent) => {
          if (!evContent) return
          const parsed2: FsmEvent[] = []
          for (const line of evContent.split('\n')) {
            const trimmed = line.trim()
            if (!trimmed) continue
            try { parsed2.push(JSON.parse(trimmed) as FsmEvent) } catch { /* skip */ }
          }
          setEvents(parsed2)
        }).catch(() => { /* file may not exist yet */ })
      } catch { /* ignore malformed */ }
    }).catch(() => { /* topic not found in any root */ })

    // STATE.json — live updates via chokidar (low frequency, keep as-is)
    watchStart(projectPath, effectiveTopic)
    const removeListener = onWatchEvent((data) => {
      if (data.path.endsWith('STATE.json')) {
        try { setFsmState(JSON.parse(data.content)) } catch { /* ignore */ }
      }
      // EVENTS.jsonl: use chokidar only when SSE has permanently closed
      if (data.path.endsWith('EVENTS.jsonl') && monitorSourceRef.current === 'chokidar') {
        const parsed: FsmEvent[] = []
        for (const line of data.content.split('\n')) {
          const trimmed = line.trim()
          if (trimmed) try { parsed.push(JSON.parse(trimmed) as FsmEvent) } catch { /* skip */ }
        }
        setEvents(parsed)
      }
    })

    // EVENTS.jsonl — live appends via SSE
    const port = 8765
    const params = new URLSearchParams({ topic: effectiveTopic, project_root: projectPath })
    const es = new EventSource(`http://127.0.0.1:${port}/events/stream?${params}`)

    es.onopen = () => setMonitorSource('sse')

    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as FsmEvent
        if (event.type === 'connected') return
        setEvents([...eventsRef.current, event])
      } catch { /* skip malformed */ }
    }

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setMonitorSource('chokidar')
        // SSE permanently closed — chokidar fallback is already active via watchStart above
      }
      // readyState === CONNECTING: browser auto-reconnecting — leave badge as-is
    }

    return () => {
      removeListener()
      es.close()
      // Do NOT delete from activeFlowSessions or reset activeMonitorTab here.
      // Session lifetime is managed by the activeTopic-change effect above,
      // so that switching tabs doesn't collapse the tab bar.
    }
  }, [effectiveTopic, projectPath, setMonitorSource, setFsmState, setEvents, setPipelineStates, setActiveFlowSessions, activeTopic])

  const showTabBar = Object.keys(activeFlowSessions).length >= 2

  if (!activeTopic) {
    return (
      <div style={styles.panel}>
        <span style={styles.placeholder}>Select a topic above to monitor</span>
      </div>
    )
  }

  return (
    <div style={styles.panel}>
      <HeaderBar effectiveTopic={effectiveTopic} />
      {showTabBar && (
        <TabBar
          sessions={activeFlowSessions}
          activeTab={activeMonitorTab}
          onTabSelect={setActiveMonitorTab}
        />
      )}
      <HealthCheck />
      <FsmView />
      <MetricsStrip />
      <EventLog />
    </div>
  )
}
