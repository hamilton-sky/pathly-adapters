import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { FsmEvent } from '../../types/index'
import { useInjectCSS, useAgentTelemetry } from './utils'

const FLASH_CSS = `
@keyframes pathly-row-flash {
  0%   { background-color: rgba(59,130,246,0.18); }
  100% { background-color: transparent; }
}
.pathly-new-row {
  animation: none;
}
@media (prefers-reduced-motion: no-preference) {
  .pathly-new-row { animation: pathly-row-flash 400ms ease-out forwards; }
}
`

function eventColor(ev: FsmEvent, t: Theme): string {
  switch (ev.type) {
    case 'STATE_TRANSITION': return t.accent
    case 'AGENT_DONE':
      if (ev.result === 'PASS') return t.green
      if (ev.result === 'DONE') return t.blue
      return t.textMuted
    case 'FILE_CREATED': return t.yellow
    case 'FILE_DELETED': return t.yellow
    case 'RETRY': return t.red
    case 'HUMAN_RESPONSE': return t.textSecondary
    case 'GATE_FAILED': return '#EF4444'
    case 'GATE_SKIPPED': return '#F59E0B'
    case 'AGENT_SPAWNED': return '#06B6D4'
    case 'STAGE_COMPLETE': return '#34D399'
    default: return t.textMuted
  }
}

function formatTime(ts?: string): string {
  if (!ts) return '--:--:--'
  try { return new Date(ts).toTimeString().slice(0, 8) } catch { return '--:--:--' }
}

function formatEvent(ev: FsmEvent, retrograde?: boolean): string {
  const ts = formatTime(ev.ts ?? ev.timestamp)
  const pad = (s: string, n: number): string => s.padEnd(n)

  switch (ev.type) {
    case 'STATE_TRANSITION': {
      const prefix = retrograde ? '↩ ' : ''
      return `${ts}  ${pad('TRANSITION', 14)}  ${prefix}${ev.from ?? '?'} → ${ev.to ?? '?'}`
    }
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
    case 'GATE_FAILED':
      return `${ts}  ${pad('GATE_FAILED', 14)}  ${ev.key ?? ev.detail ?? ''}${ev.to ? ` → ${ev.to}` : ''}`
    case 'GATE_SKIPPED':
      return `${ts}  ${pad('GATE_SKIPPED', 14)}  ${ev.key ?? ev.detail ?? ''}${ev.reason ? `  reason: ${ev.reason}` : ''}`
    case 'STAGE_COMPLETE':
      return `${ts}  ${pad('STAGE_COMPLETE', 14)}  ${ev.stage ?? ev.from ?? '?'} → ${ev.next ?? ev.to ?? '?'}`
    default: {
      const { type, ts: _ts, timestamp: _ts2, ...rest } = ev
      const extra = Object.entries(rest).map(([k, v]) => `${k}=${String(v)}`).join('  ')
      return `${ts}  ${pad(type, 14)}  ${extra}`
    }
  }
}

function RawEventLine({ ev, t, isNew, retrograde }: { ev: FsmEvent; t: Theme; isNew: boolean; retrograde?: boolean }): JSX.Element {
  const baseColor = eventColor(ev, t)
  const color = retrograde ? '#F97316' : baseColor
  return (
    <div
      className={isNew ? 'pathly-new-row' : undefined}
      style={{
        color,
        fontFamily: "'Fira Mono', 'Cascadia Code', 'Consolas', monospace",
        fontSize: '12px',
        lineHeight: '1.7',
        whiteSpace: 'pre',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        padding: '1px 0',
      }}
    >
      {formatEvent(ev, retrograde)}
    </div>
  )
}

function computeRetrograde(events: FsmEvent[]): boolean[] {
  const seen = new Set<string>()
  return events.map((ev) => {
    if (ev.type !== 'STATE_TRANSITION') return false
    const to = ev.to ?? ''
    if (!to) return false
    if (seen.has(to)) return true
    seen.add(to)
    return false
  })
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
    logWrapper: {
      flex: 1,
      position: 'relative' as const,
      display: 'flex',
      flexDirection: 'column' as const,
      overflow: 'hidden',
      minHeight: 0,
    },
    log: {
      flex: 1,
      overflowY: 'auto' as const,
      backgroundColor: t.bgTerminal,
      borderRadius: '4px',
      border: `1px solid ${t.bgSurface0}`,
      padding: '8px',
    },
    empty: {
      color: t.textMuted,
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
  const t = useTheme()
  const styles = makeStyles(t)
  const { totalIn, totalOut, totalTokens, agentDone } = useAgentTelemetry()
  const missingCostData = agentDone.length > 0 && agentDone.every((ev) => ev.cost_usd == null)

  useInjectCSS(FLASH_CSS)

  const logRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)
  const prevLengthRef = useRef(0)
  const newCountRef = useRef(0)

  const [newCount, setNewCount] = useState(0)
  const [flashStart, setFlashStart] = useState(Infinity)

  useEffect(() => {
    const added = events.length - prevLengthRef.current
    prevLengthRef.current = events.length

    if (added <= 0) return

    if (autoScrollRef.current) {
      if (logRef.current) {
        logRef.current.scrollTop = logRef.current.scrollHeight
      }
      newCountRef.current = 0
      setNewCount(0)
    } else {
      newCountRef.current += added
      setNewCount(newCountRef.current)
    }

    setFlashStart(events.length - added)

    const timer = setTimeout(() => {
      setFlashStart(Infinity)
    }, 500)

    return () => clearTimeout(timer)
  }, [events])

  const handleScroll = (): void => {
    const el = logRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (distFromBottom > 40) {
      autoScrollRef.current = false
    } else {
      autoScrollRef.current = true
      newCountRef.current = 0
      setNewCount(0)
    }
  }

  const handlePillClick = (): void => {
    const el = logRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    autoScrollRef.current = true
    newCountRef.current = 0
    setNewCount(0)
  }

  const retrogradeFlags = computeRetrograde(events)

  return (
    <div style={styles.container}>
      <div style={styles.title}>Event Log</div>
      <div style={styles.logWrapper}>
        <div ref={logRef} style={styles.log} onScroll={handleScroll}>
          {events.length === 0 ? (
            <div style={styles.empty}>No events yet</div>
          ) : (
            events.map((ev, i) => (
              <RawEventLine
                key={`${ev.ts ?? ''}-${ev.type}-${i}`}
                ev={ev}
                t={t}
                isNew={i >= flashStart}
                retrograde={retrogradeFlags[i]}
              />
            ))
          )}
        </div>
        {newCount > 0 && (
          <div
            onClick={handlePillClick}
            style={{
              position: 'absolute',
              bottom: '8px',
              right: '16px',
              backgroundColor: '#1E3A5F',
              color: '#3B82F6',
              border: '1px solid #3B82F6',
              borderRadius: 12,
              padding: '2px 10px',
              fontSize: 11,
              cursor: 'pointer',
              fontFamily: t.fontFamilyMono,
              userSelect: 'none',
            }}
          >
            ↓ {newCount} new
          </div>
        )}
      </div>
      <div style={{ ...styles.totalsBar, display: 'flex', alignItems: 'center', gap: '6px' }}>
        <span style={styles.totalsLabel}>in/out</span>
        <span style={styles.totalsValue}>
          {totalIn > 0 ? `${(totalIn / 1000).toFixed(1)}k` : '—'}↑
          &nbsp;&nbsp;
          {totalOut > 0 ? `${(totalOut / 1000).toFixed(1)}k` : '—'}↓
        </span>
        {totalTokens > 0 && (
          <span style={{ ...styles.totalsLabel, marginLeft: 'auto', opacity: 0.5, fontStyle: 'italic' }}>
            = {totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens} combined ↑
          </span>
        )}
        {missingCostData && (
          <span style={{ ...styles.totalsLabel, marginLeft: 'auto', opacity: 0.5 }}>
            (no cost data)
          </span>
        )}
      </div>
    </div>
  )
}
