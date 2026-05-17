import { useEffect } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'
import type { FsmEvent } from '../../types'
import { mcpPing, watchStart, readFile, onWatchEvent } from '../../services/pathlyApi'

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
    setEvents
  } = useStore()

  const t = useTheme()
  const styles = makeStyles(t)

  useEffect(() => {
    if (!activeTopic) return

    async function init(): Promise<void> {
      const mcpAlive = await mcpPing()
      if (mcpAlive) {
        setMonitorSource('mcp')
      } else {
        setMonitorSource('chokidar')
        watchStart(projectPath, activeTopic ?? '')
      }
    }

    init()

    if (projectPath && activeTopic) {
      const base = `${projectPath}/pathly/plans/${activeTopic}`

      readFile(`${base}/STATE.json`).then((content) => {
        if (!content) return
        try { setFsmState(JSON.parse(content)) } catch { /* ignore malformed */ }
      }).catch(() => { /* file may not exist yet */ })

      readFile(`${base}/EVENTS.jsonl`).then((content) => {
        if (!content) return
        const parsed: FsmEvent[] = []
        for (const line of content.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed) continue
          try {
            parsed.push(JSON.parse(trimmed) as FsmEvent)
          } catch {
            // skip malformed lines
          }
        }
        setEvents(parsed)
      }).catch(() => { /* file may not exist yet */ })
    }

    const removeListener = onWatchEvent((data) => {
      if (data.path.endsWith('STATE.json')) {
        try {
          setFsmState(JSON.parse(data.content))
        } catch {
          // ignore malformed JSON
        }
      } else if (data.path.endsWith('EVENTS.jsonl')) {
        try {
          const lines = data.content
            .split('\n')
            .filter((l) => l.trim() !== '')
            .slice(-50)
            .map((l) => JSON.parse(l))
          setEvents(lines)
        } catch {
          // ignore malformed JSONL
        }
      }
    })

    return () => { removeListener() }
  }, [activeTopic, projectPath, setMonitorSource, setFsmState, setEvents])

  if (!activeTopic) {
    return (
      <div style={styles.panel}>
        <span style={styles.placeholder}>Select a topic above to monitor</span>
      </div>
    )
  }

  const sourceBadge = monitorSource === 'mcp'
    ? <span style={{ ...styles.sourceBadge, color: t.green }}>Source: ● MCP live</span>
    : <span style={{ ...styles.sourceBadge, color: t.textMuted }}>Source: ○ File watch</span>

  return (
    <div style={styles.panel}>
      {sourceBadge}
      <FsmView />
      <EventLog />
    </div>
  )
}
