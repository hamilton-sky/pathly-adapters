import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { readFile } from '../services/pathlyApi'
import { useTheme } from '../useTheme'
import type { Theme } from '../theme'
import type { ConvRow } from '../types'
import { parseProgressMd } from '../hooks/usePlanConversations'
import { formatRelativeTime } from './Monitor/utils'

interface EventEntry {
  type: string
  agent?: string
  conversation?: number
  result?: string
  to?: string
  cost_usd?: number
  tokens_in?: number
  tokens_out?: number
  wall_seconds?: number
  timestamp?: string
  ts?: string
}

const COMPLETED_GREEN = '#16A34A'
const ACTIVE_CYAN = '#06B6D4'

function fsmStateColor(state: string, t: Theme): string {
  if (state === 'DONE') return t.green
  if (state === 'BUILDING' || state === 'REVIEWING') return t.runtime
  if (state === 'BLOCKED') return t.red
  return t.textMuted
}

function statusBorderColor(status: string, t: Theme): string {
  if (status === 'DONE') return COMPLETED_GREEN
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return ACTIVE_CYAN
  if (status === 'BLOCKED') return t.red
  return t.textMuted
}

function statusBgColor(status: string): string {
  if (status === 'DONE') return 'rgba(166,227,161,0.05)'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return 'rgba(34,211,238,0.05)'
  if (status === 'BLOCKED') return 'rgba(243,139,168,0.05)'
  return 'rgba(108,112,134,0.05)'
}

function statusIcon(status: string, t: Theme): { icon: string; color: string } {
  if (status === 'DONE') return { icon: '✓', color: COMPLETED_GREEN }
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING')
    return { icon: '●', color: ACTIVE_CYAN }
  if (status === 'BLOCKED') return { icon: '✗', color: t.red }
  return { icon: '○', color: t.textMuted }
}

function isActiveStatus(status: string): boolean {
  return status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING'
}

const PULSE_BORDER_CSS = `
@keyframes pathly-pulse-border {
  0%, 100% { border-left-color: ${ACTIVE_CYAN}; }
  50%       { border-left-color: rgba(6,182,212,0.15); }
}
.pathly-pulse-border { border-left-color: ${ACTIVE_CYAN}; }
@media (prefers-reduced-motion: no-preference) {
  .pathly-pulse-border { animation: pathly-pulse-border 1.5s ease-in-out infinite; }
}
`

function makeStyles(t: Theme): Record<string, React.CSSProperties> {
  return {
    container: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: t.bgBase,
      overflowY: 'auto' as const,
      height: '100%'
    },
    placeholder: {
      flex: 1,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: t.textMuted,
      fontSize: '15px',
      marginTop: '80px'
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 24px',
      borderBottom: `1px solid ${t.bgSurface0}`,
      flexShrink: 0
    },
    planName: {
      fontSize: '16px',
      fontWeight: 600,
      color: t.textPrimary
    },
    fsmBadge: {
      fontSize: '12px',
      fontWeight: 700,
      color: t.bgBase,
      padding: '2px 10px',
      borderRadius: '12px'
    },
    cardList: {
      padding: '16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '10px'
    },
    card: {
      borderRadius: '6px',
      overflow: 'hidden',
      minHeight: '52px'
    },
    eventRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '12px',
      fontFamily: 'monospace',
      color: t.textSecondary,
      padding: '2px 0'
    },
    eventType: {
      color: t.blue,
      fontWeight: 600,
      flexShrink: 0
    },
    eventAgent: {
      color: t.accent,
      flexShrink: 0
    },
    eventResult: {
      color: t.green,
      flexShrink: 0
    },
    eventCost: {
      color: t.yellow,
      flexShrink: 0
    },
    eventTime: {
      color: t.textMuted,
      fontSize: '11px',
      marginLeft: 'auto'
    },
    recentEventsSection: {
      padding: '0 24px 16px 24px',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '4px'
    },
    recentEventsHeader: {
      fontSize: '12px',
      fontWeight: 600,
      color: t.textMuted,
      textTransform: 'uppercase' as const,
      letterSpacing: '0.05em',
      marginBottom: '6px'
    }
  }
}

interface ConvCardProps {
  conv: ConvRow
  events: EventEntry[]
  isSelected: boolean
  isHovered: boolean
  onSelect: () => void
  onHoverEnter: () => void
  onHoverLeave: () => void
  t: Theme
}

function ConvCard({ conv, events, isSelected, isHovered, onSelect, onHoverEnter, onHoverLeave, t }: ConvCardProps): JSX.Element {
  const active = isActiveStatus(conv.status)
  const cardRef = useRef<HTMLDivElement>(null)
  const styleInjectedRef = useRef(false)

  // Inject pulse-border CSS once
  useEffect(() => {
    if (styleInjectedRef.current) return
    styleInjectedRef.current = true
    try {
      const el = document.createElement('style')
      el.textContent = PULSE_BORDER_CSS
      el.setAttribute('data-pathly-pulse-border', '1')
      if (!document.querySelector('[data-pathly-pulse-border]')) {
        document.head.appendChild(el)
      }
    } catch { /* CSP may block — base state has no animation, so this is safe to fail */ }
  }, [])

  // Apply/remove pulse class on active status
  useEffect(() => {
    const el = cardRef.current
    if (!el) return
    if (active) {
      el.classList.add('pathly-pulse-border')
      function onAnimEnd(): void { el?.classList.remove('pathly-pulse-border') }
      el.addEventListener('animationend', onAnimEnd, { once: true })
      return () => { el.removeEventListener('animationend', onAnimEnd) }
    }
    return undefined
  }, [active, conv.status])

  // Compute cost for this conversation (sum all AGENT_DONE events for this conv num)
  const agentDoneEvents = events.filter(
    (e) => e.type === 'AGENT_DONE' && e.conversation === conv.num
  )
  const hasCostData = agentDoneEvents.some((e) => e.cost_usd !== undefined)
  const totalCost = agentDoneEvents.reduce((sum, e) => sum + (e.cost_usd ?? 0), 0)
  const totalTokensIn = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_in ?? 0), 0)
  const totalTokensOut = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_out ?? 0), 0)

  // Latest AGENT_DONE timestamp for relative time
  const latestEvent = agentDoneEvents.length > 0
    ? agentDoneEvents[agentDoneEvents.length - 1]
    : null
  const latestTs = latestEvent?.ts ?? latestEvent?.timestamp ?? null

  const { icon, color: iconColor } = statusIcon(conv.status, t)

  const borderColor = isSelected
    ? t.accent
    : statusBorderColor(conv.status, t)
  const bgColor = isHovered || isSelected
    ? t.bgSurface1
    : statusBgColor(conv.status)

  return (
    <div
      ref={cardRef}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      style={{
        borderRadius: '6px',
        overflow: 'hidden',
        minHeight: '52px',
        borderLeft: `3px solid ${borderColor}`,
        backgroundColor: bgColor,
        cursor: 'pointer',
        outline: 'none'
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 14px',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', flex: 1, overflow: 'hidden' }}>
          <span style={{ color: iconColor, fontWeight: 700, flexShrink: 0, fontSize: '14px' }}>
            {icon}
          </span>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <div style={{ fontSize: '14px', color: t.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              Conv {conv.num} · {conv.title}
            </div>
            <div style={{ fontSize: '12px', color: t.textMuted, fontFamily: t.fontFamilyMono, marginTop: '2px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {conv.phases && <span>Phase {conv.phases}</span>}
              {latestTs && <span>{formatRelativeTime(latestTs)}</span>}
            </div>
            {hasCostData && (
              <div style={{
                fontSize: '12px',
                color: t.textMuted,
                fontFamily: t.fontFamilyMono,
                fontVariantNumeric: 'tabular-nums',
                marginTop: '2px'
              }}>
                {(totalTokensIn / 1000).toFixed(1)}k in / {(totalTokensOut / 1000).toFixed(1)}k out · ${totalCost.toFixed(3)}
              </div>
            )}
          </div>
        </div>
        <span style={{
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          color: borderColor,
          flexShrink: 0
        }}>
          {conv.status}
        </span>
      </div>
    </div>
  )
}

export function PlanBoard(): JSX.Element {
  const { projectPath, activeTopic } = useStore()
  const t = useTheme()
  const styles = makeStyles(t)

  const [fsmState, setFsmState] = useState<string>('')
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [events, setEvents] = useState<EventEntry[]>([])
  const [noProgress, setNoProgress] = useState(false)
  const [selectedConv, setSelectedConv] = useState<number | null>(null)
  const [hoveredConv, setHoveredConv] = useState<number | null>(null)

  useEffect(() => {
    if (!projectPath || !activeTopic) {
      setFsmState('')
      setConvs([])
      setEvents([])
      setNoProgress(false)
      return
    }

    const base = `${projectPath}/pathly/plans/${activeTopic}`

    async function loadAll(): Promise<void> {
      try {
        const raw = await readFile(`${base}/STATE.json`)
        const parsed = JSON.parse(raw) as { current?: string }
        setFsmState(parsed.current ?? '')
      } catch {
        setFsmState('')
      }

      try {
        const md = await readFile(`${base}/PROGRESS.md`)
        const rows = parseProgressMd(md)
        setConvs(rows)
        setNoProgress(rows.length === 0)
      } catch {
        setConvs([])
        setNoProgress(true)
      }

      try {
        const raw = await readFile(`${base}/EVENTS.jsonl`)
        const parsed: EventEntry[] = []
        for (const line of raw.split('\n')) {
          const trimmed = line.trim()
          if (!trimmed) continue
          try {
            parsed.push(JSON.parse(trimmed) as EventEntry)
          } catch {
            // skip malformed lines
          }
        }
        setEvents(parsed)
      } catch {
        setEvents([])
      }
    }

    loadAll()
  }, [projectPath, activeTopic])

  if (!activeTopic) {
    return (
      <div style={styles.container}>
        <div style={styles.placeholder}>Select a topic to view its plan</div>
      </div>
    )
  }

  if (noProgress && convs.length === 0) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <span style={styles.planName}>{activeTopic}</span>
          {fsmState && (
            <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState, t) }}>
              {fsmState}
            </span>
          )}
        </div>
        <div style={styles.placeholder}>No PROGRESS.md found for this plan</div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.planName}>{activeTopic}</span>
        {fsmState && (
          <span style={{ ...styles.fsmBadge, backgroundColor: fsmStateColor(fsmState, t) }}>
            {fsmState}
          </span>
        )}
      </div>

      <div style={styles.cardList}>
        {convs.map((conv) => (
          <ConvCard
            key={conv.num}
            conv={conv}
            events={events}
            isSelected={selectedConv === conv.num}
            isHovered={hoveredConv === conv.num}
            onSelect={() => setSelectedConv(conv.num === selectedConv ? null : conv.num)}
            onHoverEnter={() => setHoveredConv(conv.num)}
            onHoverLeave={() => setHoveredConv(null)}
            t={t}
          />
        ))}
      </div>

      {events.length > 0 && (
        <div style={styles.recentEventsSection}>
          <div style={styles.recentEventsHeader}>Recent events</div>
          {events.map((ev, i) => (
            <div key={i} style={styles.eventRow}>
              <span style={styles.eventType}>{ev.type}</span>
              {ev.agent && <span style={styles.eventAgent}>{ev.agent}</span>}
              {ev.result && <span style={styles.eventResult}>{ev.result}</span>}
              {ev.to && <span style={styles.eventResult}>→ {ev.to}</span>}
              {ev.cost_usd !== undefined && (
                <span style={styles.eventCost}>${ev.cost_usd.toFixed(4)}</span>
              )}
              <span style={styles.eventTime}>{ev.timestamp ?? ev.ts ?? ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
