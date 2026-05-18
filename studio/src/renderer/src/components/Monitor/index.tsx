import { useEffect } from 'react'
import { useStore } from '../../store'
import { useProjectStore } from '../../store/projectStore'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import type { FsmEvent } from '../../types'
import { watchStart, readFile, onWatchEvent } from '../../services/pathlyApi'

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
    }
  }
}

export function Monitor(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    monitorSource,
    setMonitorSource,
    setFsmState,
    setEvents,
    setPipelineStates
  } = useStore()

  const t = useTheme()
  const styles = makeStyles(t)

  useEffect(() => {
    if (!activeTopic) {
      setPipelineStates([])
      return
    }

    const base = `${projectPath}/pathly/plans/${activeTopic}`

    // STATE.json — initial read
    readFile(`${base}/STATE.json`).then((content) => {
      if (!content) return
      try {
        const parsed = JSON.parse(content)
        setFsmState(parsed)
        const flowName = parsed.flow as string | undefined
        if (!flowName) return
        readFile(`${projectPath}/src/pathly_data/core/flows/${flowName}.flow.yaml`)
          .then((yaml) => {
            const match = yaml.match(/states:\s*\n((?:[ \t]+-[ \t]+\S+\n?)+)/)
            if (match) {
              const states = match[1]
                .trim()
                .split('\n')
                .map((l) => l.replace(/^[ \t]+-[ \t]+/, '').trim())
                .filter(Boolean)
              setPipelineStates(states)
            }
          })
          .catch(() => { /* flow YAML missing — FsmView uses fallback */ })
      } catch { /* ignore malformed */ }
    }).catch(() => { /* file may not exist yet */ })

    // EVENTS.jsonl — initial snapshot
    readFile(`${base}/EVENTS.jsonl`).then((content) => {
      if (!content) return
      const parsed: FsmEvent[] = []
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try { parsed.push(JSON.parse(trimmed) as FsmEvent) } catch { /* skip */ }
      }
      setEvents(parsed)
    }).catch(() => { /* file may not exist yet */ })

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
        const current = useProjectStore.getState().events
        useProjectStore.getState().setEvents([...current, event])
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
      {sourceBadge}
      <FsmView />
      <EventLog />
    </div>
  )
}
