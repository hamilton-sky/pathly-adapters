import { useEffect, useRef, useState } from 'react'
import { useStore } from '../../store'
import { readFile } from '../../services/pathlyApi'
import { useTheme } from '../../useTheme'
import type { Theme } from '../../theme'
import type { ConvRow } from '../../types'
import { parseProgressMd } from '../../hooks/usePlanConversations'
import { formatRelativeTime } from '../Monitor/utils'
import {
  isActiveStatus,
  makeStyles,
  makeCardStyles,
  statusBorderColor,
  statusBgColor,
  statusIcon,
  PULSE_BORDER_CSS,
} from './PlanBoard.styles'

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
    } catch { /* CSP may block — base state has no animation, so safe to fail */ }
  }, [])

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

  const agentDoneEvents = events.filter(
    (e) => e.type === 'AGENT_DONE' && e.conversation === conv.num
  )
  const hasCostData = agentDoneEvents.some((e) => e.cost_usd !== undefined)
  const totalCost = agentDoneEvents.reduce((sum, e) => sum + (e.cost_usd ?? 0), 0)
  const totalTokensIn = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_in ?? 0), 0)
  const totalTokensOut = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_out ?? 0), 0)

  const latestEvent = agentDoneEvents[agentDoneEvents.length - 1] ?? null
  const latestTs = latestEvent?.ts ?? latestEvent?.timestamp ?? null

  const { icon, color: iconColor } = statusIcon(conv.status, t)
  const borderColor = isSelected ? t.accent : statusBorderColor(conv.status, t)
  const bgColor = isHovered || isSelected ? t.bgSurface1 : statusBgColor(conv.status)
  const cs = makeCardStyles(t, borderColor, bgColor, iconColor)

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
      style={cs.card}
    >
      <div style={cs.inner}>
        <div style={cs.left}>
          <span style={cs.statusIcon}>{icon}</span>
          <div style={cs.textBlock}>
            <div style={cs.title}>Conv {conv.num} · {conv.title}</div>
            <div style={cs.meta}>
              {conv.phases && <span>Phase {conv.phases}</span>}
              {latestTs && <span>{formatRelativeTime(latestTs)}</span>}
            </div>
            {hasCostData && (
              <div style={cs.cost}>
                {(totalTokensIn / 1000).toFixed(1)}k in / {(totalTokensOut / 1000).toFixed(1)}k out · ${totalCost.toFixed(3)}
              </div>
            )}
          </div>
        </div>
        <span style={cs.statusBadge}>{conv.status}</span>
      </div>
    </div>
  )
}

export function PlanBoard(): JSX.Element {
  const { projectPath, activeTopic } = useStore()
  const t = useTheme()
  const s = makeStyles(t)

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
          try { parsed.push(JSON.parse(trimmed) as EventEntry) } catch { /* skip malformed */ }
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
      <div style={s.container}>
        <div style={s.placeholder}>Select a topic to view its plan</div>
      </div>
    )
  }

  if (noProgress && convs.length === 0) {
    return (
      <div style={s.container}>
        <div style={s.header}>
          <span style={s.planName}>{activeTopic}</span>
          {fsmState && <span style={s.fsmBadge(fsmState)}>{fsmState}</span>}
        </div>
        <div style={s.placeholder}>No PROGRESS.md found for this plan</div>
      </div>
    )
  }

  return (
    <div style={s.container}>
      <div style={s.header}>
        <span style={s.planName}>{activeTopic}</span>
        {fsmState && <span style={s.fsmBadge(fsmState)}>{fsmState}</span>}
      </div>

      <div style={s.cardList}>
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
        <div style={s.recentEventsSection}>
          <div style={s.recentEventsHeader}>Recent events</div>
          {events.map((ev, i) => (
            <div key={i} style={s.eventRow}>
              <span style={s.eventType}>{ev.type}</span>
              {ev.agent && <span style={s.eventAgent}>{ev.agent}</span>}
              {ev.result && <span style={s.eventResult}>{ev.result}</span>}
              {ev.to && <span style={s.eventResult}>→ {ev.to}</span>}
              {ev.cost_usd !== undefined && (
                <span style={s.eventCost}>${ev.cost_usd.toFixed(4)}</span>
              )}
              <span style={s.eventTime}>{ev.timestamp ?? ev.ts ?? ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
