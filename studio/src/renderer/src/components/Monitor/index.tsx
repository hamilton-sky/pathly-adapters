import { useEffect } from 'react'
import { useStore } from '../../store'
import { FsmView } from './FsmView'
import { EventLog } from './EventLog'

export function Monitor(): JSX.Element {
  const {
    projectPath,
    activeTopic,
    setMonitorSource,
    setFsmState,
    setEvents
  } = useStore()

  useEffect(() => {
    if (!activeTopic) return

    async function init(): Promise<void> {
      const mcpAlive = await window.pathly.mcp.ping()
      if (mcpAlive) {
        setMonitorSource('mcp')
      } else {
        setMonitorSource('chokidar')
        window.pathly.watch.start(projectPath, activeTopic ?? '')
      }
    }

    init()

    const removeListener = window.pathly.watch.onEvent((data) => {
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

  return (
    <div style={styles.panel}>
      <FsmView />
      <EventLog />
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#1e1e2e',
    overflow: 'auto'
  },
  placeholder: {
    margin: 'auto',
    color: '#6c7086',
    fontSize: '15px'
  }
}
