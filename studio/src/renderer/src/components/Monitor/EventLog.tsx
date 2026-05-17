import { useEffect, useRef } from 'react'
import { useStore } from '../../store'

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toTimeString().slice(0, 8)
  } catch {
    return ts.slice(0, 8)
  }
}

export function EventLog(): JSX.Element {
  const events = useStore((s) => s.events)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  return (
    <div style={styles.container}>
      <div style={styles.title}>Event Log</div>
      <div style={styles.log}>
        {events.length === 0 ? (
          <div style={styles.empty}>No events yet</div>
        ) : (
          events.map((ev, i) => (
            <div key={i} style={styles.row}>
              <span style={styles.ts}>{formatTime(ev.ts)}</span>
              <span style={styles.type}>{ev.type}</span>
              <span style={styles.detail}>{ev.detail}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '16px'
  },
  title: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#6c7086',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  },
  log: {
    height: '300px',
    overflowY: 'auto',
    backgroundColor: '#11111b',
    borderRadius: '4px',
    border: '1px solid #313244',
    padding: '8px'
  },
  empty: {
    color: '#45475a',
    fontSize: '13px',
    textAlign: 'center',
    marginTop: '120px'
  },
  row: {
    display: 'flex',
    gap: '12px',
    fontSize: '12px',
    fontFamily: 'monospace',
    padding: '2px 0',
    borderBottom: '1px solid #1e1e2e'
  },
  ts: {
    color: '#45475a',
    flexShrink: 0,
    width: '70px'
  },
  type: {
    color: '#cba6f7',
    flexShrink: 0,
    width: '140px',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  detail: {
    color: '#cdd6f4',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  }
}
