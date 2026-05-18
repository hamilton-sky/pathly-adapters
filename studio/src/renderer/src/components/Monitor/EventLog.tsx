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

function formatTime(ts?: string): string {
  if (!ts) return '--:--:--'
  try { return new Date(ts).toTimeString().slice(0, 8) } catch { return '--:--:--' }
}

function formatEvent(ev: FsmEvent): string {
  const ts = formatTime(ev.ts ?? ev.timestamp)
  const pad = (s: string, n: number): string => s.padEnd(n)

  switch (ev.type) {
    case 'STATE_TRANSITION':
      return `${ts}  ${pad('TRANSITION', 14)}  ${ev.from ?? '?'} → ${ev.to ?? '?'}`
    case 'AGENT_DONE': {
      const conv = ev.conversation != null ? ` #${ev.conversation}` : ''
      const result = ev.result ?? ''
      const tools = ev.tool_uses != null ? `  ${ev.tool_uses} tools` : ''
      const secs = ev.wall_seconds != null ? `  ${ev.wall_seconds}s` : ''
      const cost = ev.cost_usd != null && ev.cost_usd > 0 ? `  $${ev.cost_usd.toFixed(4)}` : ''
      return `${ts}  ${pad('AGENT_DONE', 14)}  ${ev.agent ?? '?'}${conv}  ${result}${tools}${secs}${cost}`
    }
    case 'AGENT_SPAWNED':
      return `${ts}  ${pad('AGENT_SPAWNED', 14)}  ${ev.agent ?? '?'}${ev.conversation != null ? ` #${ev.conversation}` : ''}`
    case 'FILE_CREATED':
      return `${ts}  ${pad('FILE_CREATED', 14)}  ${ev.file ?? ''}`
    case 'FILE_DELETED':
      return `${ts}  ${pad('FILE_DELETED', 14)}  ${ev.file ?? ''}`
    case 'RETRY':
      return `${ts}  ${pad('RETRY', 14)}  ${ev.key ?? ev.detail ?? ''}`
    case 'HUMAN_RESPONSE':
      return `${ts}  ${pad('HUMAN_RESPONSE', 14)}  ${ev.value ?? ''}`
    case 'IMPLEMENT_COMPLETE':
      return `${ts}  IMPLEMENT_COMPLETE`
    default: {
      const { type, ts: _ts, timestamp: _ts2, ...rest } = ev
      const extra = Object.entries(rest).map(([k, v]) => `${k}=${String(v)}`).join('  ')
      return `${ts}  ${pad(type, 14)}  ${extra}`
    }
  }
}

function RawEventLine({ ev, t }: { ev: FsmEvent; t: Theme }): JSX.Element {
  const color = eventColor(ev, t)
  return (
    <div style={{
      color,
      fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
      fontSize: '12px',
      lineHeight: '1.7',
      whiteSpace: 'pre',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      padding: '1px 0',
    }}>
      {formatEvent(ev)}
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
      fontSize: '12px',
      fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
      color: t.textMuted,
    },
    totalsValue: {
      fontSize: '12px',
      fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
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
  const hasTelemetry = agentDone.length > 0

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
      <div style={styles.totalsBar}>
        <span style={styles.totalsLabel}>
          Total&nbsp;&nbsp;
          <span style={styles.totalsValue}>
            {totalIn > 0 ? `${(totalIn / 1000).toFixed(1)}k` : '—'}↑
            &nbsp;&nbsp;
            {totalOut > 0 ? `${(totalOut / 1000).toFixed(1)}k` : '—'}↓
            &nbsp;&nbsp;
            {totalCost > 0 ? `$${totalCost.toFixed(4)}` : '—'}
          </span>
          {!hasTelemetry && agentDone.length > 0 && (
            <span style={{ ...styles.totalsLabel, marginLeft: 12, opacity: 0.5 }}>
              (no telemetry — FSM needs cost_usd in AGENT_DONE events)
            </span>
          )}
        </span>
      </div>
    </div>
  )
}
