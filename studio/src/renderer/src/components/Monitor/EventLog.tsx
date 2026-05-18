import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { FsmEvent } from '../../types'

function eventColor(ev: FsmEvent, t: Theme): string {
  if (ev.type === 'STATE_TRANSITION') return t.accent
  if (ev.type === 'AGENT_DONE') {
    if (ev.result === 'PASS') return t.green
    if (ev.result === 'DONE') return t.blue
  }
  if (ev.type === 'FILE_CREATED' || ev.type === 'FILE_DELETED') return t.yellow
  if (ev.type === 'RETRY') return t.red
  if (ev.type === 'HUMAN_RESPONSE') return t.textMuted
  return t.textSecondary
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
            <div
              key={i}
              style={{
                fontFamily: 'monospace',
                fontSize: '11px',
                wordBreak: 'break-all',
                color: eventColor(ev, t),
                padding: '1px 0'
              }}
            >
              {JSON.stringify(ev)}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
