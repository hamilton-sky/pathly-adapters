import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../../store'
import { readFile } from '../../services/pathlyApi'
import type { ConvRow } from '../../types'
import { parseProgressMd } from '../../hooks/usePlanConversations'
import { formatRelativeTime } from '../Monitor/utils'
import s from './PlanBoard.module.css'

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
}

function normalizeStatus(status: string): 'done' | 'active' | 'blocked' | undefined {
  if (status === 'DONE') return 'done'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return 'active'
  if (status === 'BLOCKED') return 'blocked'
  return undefined
}

function statusIconChar(status: string): string {
  if (status === 'DONE') return '✓'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '●'
  if (status === 'BLOCKED') return '✗'
  return '○'
}

function ConvCard({ conv, events, isSelected, isHovered, onSelect, onHoverEnter, onHoverLeave }: ConvCardProps): JSX.Element {
  const dataStatus = normalizeStatus(conv.status)

  const agentDoneEvents = events.filter(
    (e) => e.type === 'AGENT_DONE' && e.conversation === conv.num
  )
  const hasCostData = agentDoneEvents.some((e) => e.cost_usd !== undefined)
  const totalCost = agentDoneEvents.reduce((sum, e) => sum + (e.cost_usd ?? 0), 0)
  const totalTokensIn = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_in ?? 0), 0)
  const totalTokensOut = agentDoneEvents.reduce((sum, e) => sum + (e.tokens_out ?? 0), 0)

  const latestEvent = agentDoneEvents[agentDoneEvents.length - 1] ?? null
  const latestTs = latestEvent?.ts ?? latestEvent?.timestamp ?? null

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect() } }}
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      className={s.card}
      data-status={dataStatus}
      data-selected={isSelected ? 'true' : 'false'}
      data-hovered={isHovered ? 'true' : 'false'}
    >
      <div className={s.cardInner}>
        <div className={s.cardLeft}>
          <span className={s.statusIcon} data-status={dataStatus}>{statusIconChar(conv.status)}</span>
          <div className={s.textBlock}>
            <div className={s.cardTitle}>Conv {conv.num} · {conv.title}</div>
            <div className={s.cardMeta}>
              {conv.phases && <span>Phase {conv.phases}</span>}
              {latestTs && <span>{formatRelativeTime(latestTs)}</span>}
            </div>
            {hasCostData && (
              <div className={s.cardCost}>
                {(totalTokensIn / 1000).toFixed(1)}k in / {(totalTokensOut / 1000).toFixed(1)}k out · ${totalCost.toFixed(3)}
              </div>
            )}
          </div>
        </div>
        <span className={s.statusBadge} data-status={dataStatus}>{conv.status}</span>
      </div>
    </div>
  )
}

export function PlanBoard(): JSX.Element {
  const { projectPath, activeTopic } = useStore()

  const [fsmState, setFsmState] = useState<string>('')
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [events, setEvents] = useState<EventEntry[]>([])
  const [noProgress, setNoProgress] = useState(false)
  const [selectedConv, setSelectedConv] = useState<number | null>(null)
  const [hoveredConv, setHoveredConv] = useState<number | null>(null)

  const loadAll = useCallback(async (): Promise<void> => {
    if (!projectPath || !activeTopic) {
      setFsmState('')
      setConvs([])
      setEvents([])
      setNoProgress(false)
      return
    }

    const base = `${projectPath}/pathly/plans/${activeTopic}`

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
  }, [projectPath, activeTopic])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!projectPath) return
    const { onWorkspaceChanged } = window.pathly.watch
    if (!onWorkspaceChanged) return
    return onWorkspaceChanged(() => { void loadAll() })
  }, [loadAll, projectPath])

  if (!activeTopic) {
    return (
      <div className={s.container}>
        <div className={s.placeholder}>Select a topic to view its plan</div>
      </div>
    )
  }

  if (noProgress && convs.length === 0) {
    return (
      <div className={s.container}>
        <div className={s.header}>
          <span className={s.planName}>{activeTopic}</span>
          {fsmState && (
            <span className={s.fsmBadge} data-fsm-state={fsmState.toLowerCase()}>{fsmState}</span>
          )}
        </div>
        <div className={s.placeholder}>No PROGRESS.md found for this plan</div>
      </div>
    )
  }

  return (
    <div className={s.container}>
      <div className={s.header}>
        <span className={s.planName}>{activeTopic}</span>
        {fsmState && (
          <span className={s.fsmBadge} data-fsm-state={fsmState.toLowerCase()}>{fsmState}</span>
        )}
      </div>

      <div className={s.cardList}>
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
          />
        ))}
      </div>

      {events.length > 0 && (
        <div className={s.recentEventsSection}>
          <div className={s.recentEventsHeader}>Recent events</div>
          {events.map((ev, i) => (
            <div key={i} className={s.eventRow}>
              <span className={s.eventType}>{ev.type}</span>
              {ev.agent && <span className={s.eventAgent}>{ev.agent}</span>}
              {ev.result && <span className={s.eventResult}>{ev.result}</span>}
              {ev.to && <span className={s.eventResult}>→ {ev.to}</span>}
              {ev.cost_usd !== undefined && (
                <span className={s.eventCost}>${ev.cost_usd.toFixed(4)}</span>
              )}
              <span className={s.eventTime}>{ev.timestamp ?? ev.ts ?? ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
