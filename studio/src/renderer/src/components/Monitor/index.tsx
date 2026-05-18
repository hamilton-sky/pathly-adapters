import { useEffect, useRef } from 'react'
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
    sourceBadge: {
      padding: '4px 12px',
      fontSize: '12px',
      flexShrink: 0
    },
    header: {
      backgroundColor: t.bgSurface0,
      borderBottom: `1px solid ${t.bgSurface1}`,
      padding: '8px 12px',
      flexShrink: 0,
      fontFamily: 'monospace',
      fontSize: '12px',
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
    }
  }
}

function HeaderBar(): JSX.Element {
  const { fsmState, events } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const flow = fsmState?.flow ?? '—'
  const topic = fsmState?.feature
    ? truncate(fsmState.feature, 32)
    : '—'
  const state = fsmState?.current ?? '—'
  const conv = fsmState?.current_conversation != null
    ? String(fsmState.current_conversation)
    : '—'

  const lastAgentEvent = [...events].reverse().find((e) => e.type === 'AGENT_SPAWNED')
  const agent = lastAgentEvent?.agent ?? '—'

  return (
    <div style={styles.header}>
      <div style={styles.headerTitle}>
        Pathly&nbsp;&nbsp;·&nbsp;&nbsp;{flow}&nbsp;&nbsp;·&nbsp;&nbsp;{topic}
      </div>
      <div style={styles.headerRow}>
        <span>State : {state}</span>
        <span>Conv : {conv}</span>
      </div>
      <div>Agent : {agent}</div>
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
    setPipelineStates
  } = useStore()

  const eventsRef = useRef(events)
  eventsRef.current = events

  const t = useTheme()
  const styles = makeStyles(t)

  useEffect(() => {
    if (!activeTopic) {
      setPipelineStates([])
      return
    }

    if (!projectPath) {
      setMonitorSource('chokidar')
      return
    }

    // Probe all three roots in parallel — use whichever has STATE.json.
    // This avoids the bootstrap race where fsmState.flow is stale/null on first load.
    const roots = [
      `${projectPath}/pathly/plans/${activeTopic}`,
      `${projectPath}/pathly/debugs/${activeTopic}`,
      `${projectPath}/pathly/explorations/${activeTopic}`,
    ]

    Promise.any(
      roots.map((r) => readFile(`${r}/STATE.json`).then((c) => ({ base: r, content: c })))
    ).then(({ base, content }) => {
      if (!content) return
      try {
        const parsed = JSON.parse(content)
        setFsmState(parsed)
        const flowName = parsed.flow as string | undefined
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
    watchStart(projectPath, activeTopic)
    const removeListener = onWatchEvent((data) => {
      if (data.path.endsWith('STATE.json')) {
        try { setFsmState(JSON.parse(data.content)) } catch { /* ignore */ }
      }
      // EVENTS.jsonl handled by SSE below — ignore here
    })

    // EVENTS.jsonl — live appends via SSE
    const port = 8765
    const params = new URLSearchParams({ topic: activeTopic, project_root: projectPath })
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
      // SSE unavailable — fall back to chokidar badge only (file watch already active)
      setMonitorSource('chokidar')
    }

    return () => {
      removeListener()
      es.close()
    }
  }, [activeTopic, projectPath, setMonitorSource, setFsmState, setEvents, setPipelineStates])

  if (!activeTopic) {
    return (
      <div style={styles.panel}>
        <span style={styles.placeholder}>Select a topic above to monitor</span>
      </div>
    )
  }

  const sourceBadge = monitorSource === 'sse'
    ? <span style={{ ...styles.sourceBadge, color: t.green }}>● Live</span>
    : <span style={{ ...styles.sourceBadge, color: t.textMuted }}>○ File watch</span>

  return (
    <div style={styles.panel}>
      <HeaderBar />
      {sourceBadge}
      <FsmView />
      <EventLog />
    </div>
  )
}
