import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import type { FsmEvent } from '../../types/index'
import { useInjectCSS, useAgentTelemetry } from './utils'
import styles from './Monitor.module.css'

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

function eventColorClass(ev: FsmEvent, retrograde?: boolean): string {
  if (retrograde) return styles.evColorRetrograde
  switch (ev.type) {
    case 'STATE_TRANSITION': return styles.evColorAccent
    case 'AGENT_DONE':
      if (ev.result === 'PASS') return styles.evColorGreen
      if (ev.result === 'DONE') return styles.evColorBlue
      return styles.evColorMuted
    case 'FILE_CREATED':
    case 'FILE_DELETED':   return styles.evColorYellow
    case 'RETRY':          return styles.evColorRed
    case 'HUMAN_RESPONSE': return styles.evColorSecondary
    case 'GATE_FAILED':    return styles.evColorGateFail
    case 'GATE_SKIPPED':   return styles.evColorGateSkip
    case 'AGENT_SPAWNED':  return styles.evColorSpawned
    case 'STAGE_COMPLETE': return styles.evColorStage
    default:               return styles.evColorMuted
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

function RawEventLine({ ev, isNew, retrograde }: { ev: FsmEvent; isNew: boolean; retrograde?: boolean }): JSX.Element {
  return (
    <div className={`${styles.evLine} ${eventColorClass(ev, retrograde)} ${isNew ? 'pathly-new-row' : ''}`}>
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

export function EventLog(): JSX.Element {
  const events = useStore((s) => s.events)
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
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
      newCountRef.current = 0
      setNewCount(0)
    } else {
      newCountRef.current += added
      setNewCount(newCountRef.current)
    }

    setFlashStart(events.length - added)
    const timer = setTimeout(() => { setFlashStart(Infinity) }, 500)
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
    <div className={styles.evContainer}>
      <div className={styles.evTitle}>Event Log</div>
      <div className={styles.evLogWrapper}>
        <div ref={logRef} className={styles.evLog} onScroll={handleScroll}>
          {events.length === 0 ? (
            <div className={styles.evEmpty}>No events yet</div>
          ) : (
            events.map((ev, i) => (
              <RawEventLine
                key={`${ev.ts ?? ''}-${ev.type}-${i}`}
                ev={ev}
                isNew={i >= flashStart}
                retrograde={retrogradeFlags[i]}
              />
            ))
          )}
        </div>
        {newCount > 0 && (
          <div className={styles.evNewPill} onClick={handlePillClick}>
            ↓ {newCount} new
          </div>
        )}
      </div>
      <div className={styles.evTotalsBar}>
        <span className={styles.evTotalsLabel}>in/out</span>
        <span className={styles.evTotalsValue}>
          {totalIn > 0 ? `${(totalIn / 1000).toFixed(1)}k` : '—'}↑
          &nbsp;&nbsp;
          {totalOut > 0 ? `${(totalOut / 1000).toFixed(1)}k` : '—'}↓
        </span>
        {totalTokens > 0 && (
          <span className={`${styles.evTotalsLabel} ${styles.evTotalsSummary}`}>
            = {totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens} combined ↑
          </span>
        )}
        {missingCostData && (
          <span className={`${styles.evTotalsLabel} ${styles.evTotalsMissing}`}>
            (no cost data)
          </span>
        )}
      </div>
    </div>
  )
}
