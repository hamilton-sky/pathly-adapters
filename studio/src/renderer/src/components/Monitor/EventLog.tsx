import { useEffect, useRef } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { FsmEvent } from '../../types'

function getTs(ev: FsmEvent): string {
  const raw = ev.ts ?? ev.timestamp
  if (!raw) return '——:——:——'
  const d = new Date(raw)
  if (isNaN(d.getTime())) return '——:——:——'
  return d.toTimeString().slice(0, 8)
}

function fmtSeconds(s?: number): string {
  if (s == null) return ''
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

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
    case 'PLAN_CREATED': return t.accent
    case 'NO_DIFF_DETECTED': return t.red
    default: return t.textSecondary
  }
}

function EventRow({ ev, t }: { ev: FsmEvent; t: Theme }): JSX.Element {
  const color = eventColor(ev, t)
  const ts = getTs(ev)

  const tsStyle: React.CSSProperties = {
    color: t.textMuted,
    flexShrink: 0,
    width: '70px',
    fontFamily: 'monospace',
    fontSize: '11px',
  }
  const badgeStyle: React.CSSProperties = {
    color,
    fontFamily: 'monospace',
    fontSize: '11px',
    flexShrink: 0,
  }
  const detailStyle: React.CSSProperties = {
    color: t.textPrimary,
    fontFamily: 'monospace',
    fontSize: '11px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }
  const rowStyle: React.CSSProperties = {
    display: 'flex',
    gap: '10px',
    padding: '2px 0',
    borderBottom: `1px solid ${t.bgBase}`,
    alignItems: 'baseline',
  }

  let badge = ev.type
  let detail = ''

  switch (ev.type) {
    case 'STATE_TRANSITION':
      badge = '→'
      detail = `${ev.from ?? '?'}  →  ${ev.to ?? '?'}`
      break

    case 'AGENT_DONE': {
      const result = ev.result ?? '?'
      const conv = ev.conversation != null ? `conv ${ev.conversation}` : ''
      const tools = ev.tool_uses != null ? `${ev.tool_uses} tools` : ''
      const dur = fmtSeconds(ev.wall_seconds)
      badge = `${ev.agent ?? 'agent'}${conv ? `  ·  ${conv}` : ''}`
      detail = [result, tools, dur].filter(Boolean).join('  ·  ')
      break
    }

    case 'FILE_CREATED':
      badge = '+'
      detail = ev.file ?? ''
      break

    case 'FILE_DELETED':
      badge = '−'
      detail = ev.file ?? ''
      break

    case 'RETRY':
      badge = '↺'
      detail = ev.key ?? ''
      break

    case 'HUMAN_RESPONSE':
      badge = '✓'
      detail = ev.value ?? ''
      break

    case 'PLAN_CREATED':
      badge = '◆'
      detail = ev.note ?? 'plan created'
      break

    case 'NO_DIFF_DETECTED':
      badge = '!'
      detail = 'zero-diff stall detected'
      break

    default:
      badge = ev.type.toLowerCase().replace(/_/g, ' ')
      detail = ev.detail ?? ''
  }

  return (
    <div style={rowStyle}>
      <span style={tsStyle}>{ts}</span>
      <span style={{ ...badgeStyle, minWidth: '160px' }}>{badge}</span>
      <span style={detailStyle}>{detail}</span>
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
          events.map((ev, i) => <EventRow key={i} ev={ev} t={t} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
