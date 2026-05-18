import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { FsmEvent } from '../../types'

function eventColor(ev: FsmEvent, t: Theme): string {
  switch (ev.type) {
    case 'STATE_TRANSITION': return t.accent
    case 'AGENT_DONE':
      if (ev.result === 'PASS') return t.green
      if (ev.result === 'DONE') return t.blue
      return t.textSecondary
    case 'FILE_CREATED': return t.yellow
    case 'FILE_DELETED': return t.yellow
    case 'RETRY': return t.red
    case 'HUMAN_RESPONSE': return t.textMuted
    default: return t.textSecondary
  }
}

function RawEventLine({ ev, t }: { ev: FsmEvent; t: Theme }): JSX.Element {
  const color = eventColor(ev, t)
  return (
    <div style={{
      color,
      fontFamily: 'monospace',
      fontSize: '11px',
      lineHeight: '1.6',
      whiteSpace: 'pre',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      padding: '1px 0',
    }}>
      {JSON.stringify(ev)}
    </div>
  )
}

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      padding: '16px',
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    },
    title: {
      fontSize: '13px',
      fontWeight: 600,
      color: t.textMuted,
      marginBottom: '8px',
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
    },
    log: {
      flex: 1,
      overflowY: 'auto' as const,
      backgroundColor: t.bgMantle,
      borderRadius: '4px',
      border: `1px solid ${t.bgSurface0}`,
      padding: '8px',
    },
    empty: {
      color: t.bgSurface1,
      fontSize: '13px',
      textAlign: 'center' as const,
      marginTop: '120px',
    },
    totalsBar: {
      display: 'flex',
      gap: '20px',
      padding: '6px 8px',
      borderTop: `1px solid ${t.bgSurface0}`,
      backgroundColor: t.bgMantle,
      borderRadius: '0 0 4px 4px',
      flexShrink: 0,
    },
    totalsLabel: {
      fontSize: '11px',
      fontFamily: 'monospace',
      color: t.textMuted,
    },
    totalsValue: {
      fontSize: '11px',
      fontFamily: 'monospace',
      color: t.textSecondary,
    },
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

  const agentDone = events.filter((e) => e.type === 'AGENT_DONE')
  const totalIn = agentDone.reduce((s, e) => s + (e.tokens_in ?? 0), 0)
  const totalOut = agentDone.reduce((s, e) => s + (e.tokens_out ?? 0), 0)
  const totalCost = agentDone.reduce((s, e) => s + (e.cost_usd ?? 0), 0)
  const hasTelemetry = totalIn > 0 || totalOut > 0 || totalCost > 0

  return (
    <div style={styles.container}>
      <div style={styles.title}>Event Log</div>
      <div style={styles.log}>
        {events.length === 0 ? (
          <div style={styles.empty}>No events yet</div>
        ) : (
          events.map((ev, i) => <RawEventLine key={i} ev={ev} t={t} />)
        )}
        <div ref={bottomRef} />
      </div>
      {hasTelemetry && (
        <div style={styles.totalsBar}>
          <span style={styles.totalsLabel}>
            Total&nbsp;&nbsp;
            <span style={styles.totalsValue}>
              {(totalIn / 1000).toFixed(1)}k↑&nbsp;&nbsp;{(totalOut / 1000).toFixed(1)}k↓
              {totalCost > 0 && <>&nbsp;&nbsp;${totalCost.toFixed(4)}</>}
            </span>
          </span>
        </div>
      )}
    </div>
  )
}
