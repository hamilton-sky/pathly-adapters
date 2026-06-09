import { useEffect, useMemo, useRef, useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
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

type PhaseFilter = 'all' | 'build' | 'review'

const INNER_PHASES = new Set(['analyze', 'scout', 'implement'])
const BUILD_PHASES  = new Set(['STORMING', 'PLANNING', 'DESIGNING', 'BUILDING'])
const REVIEW_PHASES = new Set(['REVIEWING', 'TESTING', 'RETRO'])

function eventColorClass(ev: FsmEvent, retrograde?: boolean): string {
  if (retrograde) return styles.evColorRetrograde
  switch (ev.type) {
    case 'STATE_TRANSITION': return styles.evColorAccent
    case 'AGENT_DONE':
      if (ev.result === 'PASS') return styles.evColorGreen
      if (ev.result === 'DONE') return styles.evColorBlue
      return styles.evColorMuted
    case 'PHASE_START':
    case 'PHASE_DONE': {
      const phase = (ev as Record<string, unknown>).phase as string | undefined ?? ''
      return INNER_PHASES.has(phase) ? styles.evColorMuted : styles.evColorPhase
    }
    case 'FILE_CREATED':
    case 'FILE_DELETED':   return styles.evColorYellow
    case 'RETRY':          return styles.evColorRed
    case 'HUMAN_RESPONSE': return styles.evColorSecondary
    case 'GATE_FAILED':    return styles.evColorGateFail
    case 'GATE_SKIPPED':   return styles.evColorGateSkip
    case 'AGENT_SPAWNED':  return styles.evColorSpawned
    case 'STAGE_COMPLETE':
    case 'IMPLEMENT_COMPLETE': return styles.evColorStage
    case 'WARNING':        return styles.evColorYellow
    case 'PHASE_SUMMARY':  return styles.evColorSummary
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
      const tIn = ev.tokens_in ?? 0
      const tOut = ev.tokens_out ?? 0
      const total = (ev as Record<string, unknown>).total_tokens as number | undefined ?? 0
      let tokStr = ''
      if (tIn > 0 || tOut > 0) {
        tokStr = `  ${(tIn / 1000).toFixed(1)}k↑${(tOut / 1000).toFixed(1)}k↓`
      } else if (total > 0) {
        tokStr = `  ${(total / 1000).toFixed(1)}k`
      }
      return `${ts}  ${pad('AGENT_DONE', 14)}  ${ev.agent ?? '?'}${conv}  ${result}${tools}${secs}${tokStr}`
    }
    case 'PHASE_START': {
      const phase = (ev as Record<string, unknown>).phase as string | undefined ?? '?'
      const agent = (ev as Record<string, unknown>).agent as string | undefined ?? '?'
      const conv = (ev as Record<string, unknown>).conv as number | undefined
      const convSuffix = conv != null ? ` #${conv}` : ''
      if (INNER_PHASES.has(phase)) {
        return `${ts}  ${pad('·', 14)}  ${phase}`
      }
      return `${ts}  ${pad('PHASE', 14)}  ${agent}${convSuffix}  ${phase} ▸`
    }
    case 'PHASE_DONE': {
      const phase = (ev as Record<string, unknown>).phase as string | undefined ?? '?'
      const agent = (ev as Record<string, unknown>).agent as string | undefined ?? '?'
      const conv = (ev as Record<string, unknown>).conv as number | undefined
      const convSuffix = conv != null ? ` #${conv}` : ''
      if (INNER_PHASES.has(phase)) {
        return `${ts}  ${pad('·', 14)}  ${phase} done`
      }
      return `${ts}  ${pad('PHASE', 14)}  ${agent}${convSuffix}  ${phase} ✓`
    }
    case 'WARNING': {
      const reason = (ev as Record<string, unknown>).reason as string | undefined ?? 'unknown'
      const SUPPRESS = new Set(['schema_version', 'type', 'ts', 'timestamp', 'reason'])
      const diag = Object.entries(ev as Record<string, unknown>)
        .filter(([k]) => !SUPPRESS.has(k))
        .map(([k, v]) => `${k}=${String(v)}`)
        .join('  ')
      return `${ts}  ${pad('WARNING', 14)}  ${reason}${diag ? `  (${diag})` : ''}`
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
    case 'IMPLEMENT_COMPLETE': {
      const stage = (ev as Record<string, unknown>).stage as string | undefined
      return `${ts}  ${pad('IMPLEMENT_COMPLETE', 18)}  ${stage ? `${stage} complete` : 'all conversations done'}`
    }
    case 'GATE_FAILED':
      return `${ts}  ${pad('GATE_FAILED', 14)}  ${ev.key ?? ev.detail ?? ''}${ev.to ? ` → ${ev.to}` : ''}`
    case 'GATE_SKIPPED':
      return `${ts}  ${pad('GATE_SKIPPED', 14)}  ${ev.key ?? ev.detail ?? ''}${ev.reason ? `  reason: ${ev.reason}` : ''}`
    case 'STAGE_COMPLETE':
      return `${ts}  ${pad('STAGE_COMPLETE', 14)}  ${ev.stage ?? ev.from ?? '?'} → ${ev.next ?? ev.to ?? '?'}`
    case 'PHASE_SUMMARY': {
      const agent = (ev as Record<string, unknown>).agent as string | undefined ?? '?'
      const text = (ev as Record<string, unknown>).text as string | undefined ?? '(no text)'
      return `${ts}  ${pad('SUMMARY', 14)}  ${agent}  ${text}`
    }
    default: {
      const {
        type,
        ts: _ts,
        timestamp: _ts2,
        schema_version: _sv,
        feature: _feat,
        ...rest
      } = ev as Record<string, unknown>
      const extra = Object.entries(rest).map(([k, v]) => `${k}=${String(v)}`).join('  ')
      return `${ts}  ${pad(String(type), 14)}  ${extra}`
    }
  }
}

function getEventActor(ev: FsmEvent): string | null {
  switch (ev.type) {
    case 'AGENT_DONE':
    case 'AGENT_SPAWNED':
      return ev.agent ?? null
    case 'PHASE_START':
    case 'PHASE_DONE':
    case 'PHASE_SUMMARY':
      return (ev as Record<string, unknown>).agent as string | null ?? null
    default:
      return null
  }
}

function getEventCost(ev: FsmEvent): string | null {
  if (ev.type !== 'AGENT_DONE' || ev.cost_usd == null) return null
  return ev.cost_usd > 0 ? `$${ev.cost_usd.toFixed(4)}` : '$…'
}

function getActorChipClass(actor: string): string {
  if (actor.startsWith('builder'))  return styles.evActorChipBuilder
  if (actor.startsWith('reviewer')) return styles.evActorChipReviewer
  if (actor.startsWith('planner'))  return styles.evActorChipPlanner
  if (actor.startsWith('tester'))   return styles.evActorChipTester
  if (actor.startsWith('designer')) return styles.evActorChipDesigner
  if (actor.startsWith('retro'))    return styles.evActorChipRetro
  return styles.evActorChipDefault
}

function RawEventLine({ ev, isNew, retrograde }: { ev: FsmEvent; isNew: boolean; retrograde?: boolean }): JSX.Element {
  const actor = getEventActor(ev)
  const cost  = getEventCost(ev)
  return (
    <div className={`${styles.evLineRow} ${isNew ? 'pathly-new-row' : ''}`}>
      {actor && <span className={`${styles.evActorChip} ${getActorChipClass(actor)}`}>{actor}</span>}
      <span className={`${styles.evLineText} ${eventColorClass(ev, retrograde)}`}>
        {formatEvent(ev, retrograde)}
      </span>
      {cost && <span className={styles.evCostChip}>{cost}</span>}
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
  const billingPending = agentDone.length > 0 && agentDone.every((ev) => ev.cost_usd === 0)
  const missingCostData = agentDone.length > 0 && agentDone.every((ev) => ev.cost_usd == null)
  const [densePhases, setDensePhases] = useState(true)
  const [phaseFilter, setPhaseFilter] = useState<PhaseFilter>('all')

  function pillActive(f: PhaseFilter): string {
    if (phaseFilter !== f) return ''
    if (f === 'all')    return styles.phaseFilterPillActiveAll
    if (f === 'build')  return styles.phaseFilterPillActiveBuild
    return styles.phaseFilterPillActiveReview
  }

  useInjectCSS(FLASH_CSS)

  const logRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)
  const prevLengthRef = useRef(0)
  const newCountRef = useRef(0)

  const [newCount, setNewCount] = useState(0)
  const [flashStart, setFlashStart] = useState(Infinity)

  const visibleEvents = densePhases
    ? events.filter((ev) => {
        if (ev.type !== 'PHASE_START' && ev.type !== 'PHASE_DONE') return true
        const phase = (ev as Record<string, unknown>).phase as string | undefined ?? ''
        return !INNER_PHASES.has(phase)
      })
    : events

  const displayEvents = useMemo(() => {
    if (phaseFilter === 'all') return visibleEvents
    const targetSet = phaseFilter === 'build' ? BUILD_PHASES : REVIEW_PHASES
    const BUILD_ACTORS  = new Set(['builder', 'planner', 'designer'])
    const REVIEW_ACTORS = new Set(['reviewer', 'tester', 'retro'])
    const targetActors  = phaseFilter === 'build' ? BUILD_ACTORS : REVIEW_ACTORS

    // Primary: track phase via STATE_TRANSITION events
    let phase: string | null = null
    let hasTransitions = false
    const stateFiltered: typeof visibleEvents = []
    for (const ev of visibleEvents) {
      if (ev.type === 'STATE_TRANSITION' && ev.to) { phase = String(ev.to); hasTransitions = true }
      if (phase != null && targetSet.has(phase)) stateFiltered.push(ev)
    }
    if (hasTransitions) return stateFiltered

    // Fallback: infer stream from most-recently-seen agent actor
    let currentActor: string | null = null
    return visibleEvents.filter((ev) => {
      const actor = getEventActor(ev)
      if (actor) {
        const base = actor.split(' ')[0]
        if (BUILD_ACTORS.has(base) || REVIEW_ACTORS.has(base)) currentActor = base
      }
      return currentActor != null && targetActors.has(currentActor)
    })
  }, [phaseFilter, visibleEvents])

  useEffect(() => {
    const added = displayEvents.length - prevLengthRef.current
    prevLengthRef.current = displayEvents.length

    if (added <= 0) return

    if (autoScrollRef.current) {
      if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
      newCountRef.current = 0
      setNewCount(0)
    } else {
      newCountRef.current += added
      setNewCount(newCountRef.current)
    }

    setFlashStart(displayEvents.length - added)
    const timer = setTimeout(() => { setFlashStart(Infinity) }, 500)
    return () => clearTimeout(timer)
  }, [displayEvents])

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

  const retrogradeFlags = computeRetrograde(displayEvents)
  const tokPctIn = (totalIn > 0 || totalOut > 0) ? Math.round((totalIn / (totalIn + totalOut)) * 100) : 50

  return (
    <div className={styles.evContainer}>
      <div className={styles.evTitleRow}>
        <span className={styles.evTitle}>Event Log</span>
        <div className={styles.phaseFilter}>
          {(['all', 'build', 'review'] as const).map((f) => (
            <button
              key={f}
              type="button"
              className={`${styles.phaseFilterPill} ${pillActive(f)}`}
              onClick={() => setPhaseFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
        <button
          type="button"
          className={styles.evDenseToggle}
          onClick={() => setDensePhases((v) => !v)}
          aria-label={densePhases ? 'Show verbose events' : 'Show dense events'}
          title={densePhases ? 'verbose' : 'dense'}
        >
          {densePhases ? <Eye size={14} /> : <EyeOff size={14} />}
          <span>{densePhases ? 'verbose' : 'dense'}</span>
        </button>
      </div>
      <div className={styles.evLogWrapper}>
        <div ref={logRef} className={styles.evLog} onScroll={handleScroll}>
          {displayEvents.length === 0 ? (
            <div className={styles.evEmpty}>{phaseFilter !== 'all' ? `No ${phaseFilter} events` : 'No events yet'}</div>
          ) : (
            displayEvents.map((ev, i) => (
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
        <div className={styles.evTotalsRow}>
          {(totalIn > 0 || totalOut > 0) ? (
            <span className={styles.evTotalsValue}>
              {`${(totalIn / 1000).toFixed(1)}k in`}
              <span className={styles.evTotalsDot}> · </span>
              {`${(totalOut / 1000).toFixed(1)}k out`}
            </span>
          ) : totalTokens > 0 ? (
            <span className={styles.evTotalsValue}>
              {`${(totalTokens / 1000).toFixed(1)}k tokens`}
            </span>
          ) : (
            <span className={styles.evTotalsLabel}>no token data yet</span>
          )}
          {totalTokens > 0 && (
            <span className={`${styles.evTotalsLabel} ${styles.evTotalsSummary}`}>
              = {totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens} combined
            </span>
          )}
          {billingPending && !missingCostData && (
            <span className={`${styles.evTotalsLabel} ${styles.evTotalsPending}`}>(billing pending)</span>
          )}
          {missingCostData && (
            <span className={`${styles.evTotalsLabel} ${styles.evTotalsMissing}`}>(no cost data)</span>
          )}
        </div>
        {(totalIn > 0 || totalOut > 0) && (
          <div className={styles.evTokBarWrap}>
            <progress
              className={styles.evTokBar}
              value={tokPctIn}
              max={100}
              aria-label={`${(totalIn / 1000).toFixed(1)}k tokens in · ${(totalOut / 1000).toFixed(1)}k tokens out`}
            />
            <div className={styles.evTokBarLabels}>
              <span className={styles.evTokBarIn}>{`${(totalIn / 1000).toFixed(1)}k in`}</span>
              <span className={styles.evTokBarOut}>{`${(totalOut / 1000).toFixed(1)}k out`}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
