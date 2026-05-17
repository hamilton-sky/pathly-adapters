import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toTimeString().slice(0, 8)
  } catch {
    return ts.slice(0, 8)
  }
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      padding: '16px',
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    },
    title: {
      fontSize: '13px',
      fontWeight: 600,
      color: t.textMuted,
      marginBottom: '8px',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em'
    },
    log: {
      flex: 1,
      overflowY: 'auto' as const,
      backgroundColor: t.bgMantle,
      borderRadius: '4px',
      border: `1px solid ${t.bgSurface0}`,
      padding: '8px'
    },
    empty: {
      color: t.bgSurface1,
      fontSize: '13px',
      textAlign: 'center' as const,
      marginTop: '120px'
    },
    row: {
      display: 'flex',
      gap: '12px',
      fontSize: '12px',
      fontFamily: 'monospace',
      padding: '2px 0',
      borderBottom: `1px solid ${t.bgBase}`
    },
    ts: {
      color: t.bgSurface1,
      flexShrink: 0,
      width: '70px'
    },
    type: {
      color: t.accent,
      flexShrink: 0,
      width: '140px',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    },
    detail: {
      color: t.textPrimary,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap' as const
    }
  }
}

export function EventLog(): JSX.Element {
  const events = useStore((s) => s.events)
  const bottomRef = useRef<HTMLDivElement>(null)
  const t = useTheme()
  const styles = makeStyles(t)

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
