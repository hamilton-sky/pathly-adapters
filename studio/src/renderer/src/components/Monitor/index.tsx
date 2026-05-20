import { useEffect, useRef, useCallback } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import type { FsmEvent } from '../../types'
import { watchStart, readFile, onWatchEvent } from '../../services/pathlyApi'

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

function HeaderBar(): JSX.Element {
  const { fsmState, events, activeTopic, monitorSource } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const flow = fsmState?.flow ?? '—'
  const topic = fsmState?.feature
    ? truncate(fsmState.feature as string, 32)
    : activeTopic ? truncate(activeTopic, 32) : '—'
  const state = fsmState?.current ?? '—'
  const conv = fsmState?.conv != null
    ? String(fsmState.conv)
    : fsmState?.current_conversation != null
      ? String(fsmState.current_conversation)
      : '—'

  const lastAgentEvent = [...events].reverse().find((e) => e.type === 'AGENT_SPAWNED')
  const agent = lastAgentEvent?.agent ?? '—'

  const badgeText = monitorSource === 'sse' ? '● live'
    : monitorSource === 'chokidar' ? '○ polling' : '—'
  const badgeColor = monitorSource === 'sse' ? t.runtime : t.textMuted
  const badgeAriaLabel = monitorSource === 'sse' ? 'Live connection'
    : monitorSource === 'chokidar' ? 'Polling for updates' : 'Not connected'

  return (
    <div style={styles.header}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div style={styles.headerTitle}>
          Pathly&nbsp;&nbsp;·&nbsp;&nbsp;{flow}&nbsp;&nbsp;·&nbsp;&nbsp;{topic}
        </div>
        <span
          role="status"
          aria-live="polite"
          aria-atomic={true}
          aria-label={badgeAriaLabel}
          style={{ fontSize: t.fontSizeSm, color: badgeColor, marginLeft: '8px' }}
        >
          <span aria-hidden="true">{badgeText}</span>
        </span>
      </div>
      <div style={styles.headerRow}>
        <span><span style={{ color: t.textMuted }}>State</span>&nbsp;&nbsp;{state}</span>
        <span><span style={{ color: t.textMuted }}>Conv</span>&nbsp;&nbsp;{conv}</span>
        <span><span style={{ color: t.textMuted }}>Agent</span>&nbsp;&nbsp;{agent}</span>
      </div>
    </div>
  )
}

interface TabBarProps {
  sessions: Record<string, import('../../types').FlowSession>
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

  return (
    <div
      role="tablist"
      aria-label="Active flows"
      style={styles.tabBar}
    >
      {visible.map((topic, idx) => {
        const session = sessions[topic]
        const isActive = activeTab === topic || (activeTab === null && idx === 0)
        return (
          <button
            key={topic}
            role="tab"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            onClick={() => onTabSelect(topic)}
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
            {session.flowKey.replace('.flow.yaml', '')}
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

export function Monitor(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    events,
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

  const t = useTheme()
  const styles = makeStyles(t)

  // Derive effective topic: prefer active tab if valid, else fall back to activeTopic (EC-4.3)
  const effectiveTopic = (activeMonitorTab && activeFlowSessions[activeMonitorTab])
    ? activeMonitorTab
    : activeTopic

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

        // Upsert session into activeFlowSessions
        if (activeTopic) {
          setActiveFlowSessions((prev) => ({
            ...prev,
            [activeTopic]: {
              flowKey: `${(parsedState.flow as string | undefined) ?? 'team'}.flow.yaml`,
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
      // EVENTS.jsonl handled by SSE below — ignore here
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
      // Remove session on cleanup
      if (activeTopic) {
        setActiveFlowSessions((prev) => {
          const next = { ...prev }
          delete next[activeTopic]
          return next
        })
        // If the tab being cleaned up was active, revert to activeTopic path (EC-4.2)
        setActiveMonitorTab(null)
      }
    }
  }, [effectiveTopic, activeMonitorTab, projectPath, setMonitorSource, setFsmState, setEvents, setPipelineStates, setActiveFlowSessions, setActiveMonitorTab, activeTopic])

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
      <HeaderBar />
      {showTabBar && (
        <TabBar
          sessions={activeFlowSessions}
          activeTab={activeMonitorTab}
          onTabSelect={setActiveMonitorTab}
        />
      )}
      <FsmView />
      <EventLog />
    </div>
  )
}
