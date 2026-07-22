import { useCallback, useEffect, useState } from 'react'
import { useStore } from '../../store'
import { readFile } from '../../services/pathlyApi'
import { fetchDbFeatureMap } from '../../store/commsApi'
import type { ConvRow } from '../../types'
import { parseProgressMd } from '../../hooks/usePlanConversations'
import { formatRelative } from '../../utils/timestamp'
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
  isNext: boolean
  isFuture: boolean
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

function statusIconChar(status: string, isNext: boolean): string {
  if (status === 'DONE') return '✓'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return '●'
  if (status === 'BLOCKED') return 'x'
  if (isNext) return '>'
  return '○'
}

function badgeLabel(status: string, isNext: boolean): string {
  if (status === 'DONE') return 'done'
  if (status === 'BLOCKED') return 'blocked'
  if (status === 'IN_PROGRESS' || status === 'REVIEWING' || status === 'BUILDING') return status.toLowerCase().replace('_', ' ')
  if (isNext) return 'next'
  return 'todo'
}

function badgeType(status: string, isNext: boolean): string {
  const ns = normalizeStatus(status)
  if (ns) return ns
  if (isNext) return 'next'
  return 'todo'
}

function ConvCard({ conv, events, isSelected, isHovered, isNext, isFuture, onSelect, onHoverEnter, onHoverLeave }: ConvCardProps): JSX.Element {
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

  const statsLine = [
    hasCostData ? `${(totalTokensIn / 1000).toFixed(1)}k in · ${(totalTokensOut / 1000).toFixed(1)}k out · $${totalCost.toFixed(3)}` : null,
    latestTs ? formatRelative(latestTs) : null,
  ].filter(Boolean).join(' · ')

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
      data-next={isNext ? 'true' : undefined}
      data-future={isFuture ? 'true' : undefined}
    >
      <div className={s.cardInner}>
        <div className={s.cardLeft}>
          <span className={s.statusIcon} data-status={dataStatus} data-next={isNext ? 'true' : undefined}>
            {statusIconChar(conv.status, isNext)}
          </span>
          <div className={s.textBlock}>
            <div className={s.cardTitle}>
              <span className={s.convNum}
                data-status={dataStatus}
                data-selected={isSelected ? 'true' : 'false'}
                data-next={isNext ? 'true' : undefined}
              >
                Conv {conv.num}
              </span>
              {conv.title && <span className={s.convPhase}> · {conv.title}</span>}
            </div>
            {statsLine && <div className={s.cardStats}>{statsLine}</div>}
          </div>
        </div>
        <span className={s.statusBadge} data-badge={badgeType(conv.status, isNext)}>
          {badgeLabel(conv.status, isNext)}
        </span>
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

    const base = `${projectPath}/pathly/features/${activeTopic}`

    // DB-first (state-one-authority): stage comes from the /db/features row, not STATE.json.
    // fresh:true because loadAll is watcher-triggered — the DB is already ahead of the disk
    // export when the workspace-change event fires.
    try {
      const row = (await fetchDbFeatureMap(projectPath, { fresh: true })).get(activeTopic)
      setFsmState(row && row.state !== 'UNKNOWN' ? row.state : '')
    } catch {
      setFsmState('')
    }

    try {
      const md = await readFile(`${base}/PROGRESS.md`)
      const rows = parseProgressMd(md ?? '')
      setConvs(rows)
      setNoProgress(rows.length === 0)
    } catch {
      setConvs([])
      setNoProgress(true)
    }

    // DB-first (state-one-authority): events come from the /db/features/<feature>/events
    // IPC, not EVENTS.jsonl. The route returns newest-first; reverse to the chronological
    // order the cards expect. Each row's payload IS the event dict the jsonl lines held.
    try {
      const rows = await window.pathly.db.events(activeTopic, projectPath)
      const parsed = (rows ?? [])
        .map((r) => ({ ts: r.ts, type: r.event_type, ...(r.payload as Partial<EventEntry>) }) as EventEntry)
        .reverse()
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

  const activeStatuses = new Set(['IN_PROGRESS', 'REVIEWING', 'BUILDING'])
  const doneCount = convs.filter((c) => c.status === 'DONE').length
  const pct = convs.length > 0 ? Math.round((doneCount / convs.length) * 100) : 0

  const nextConvIdx = convs.findIndex(
    (c) => c.status !== 'DONE' && !activeStatuses.has(c.status) && c.status !== 'BLOCKED'
  )

  return (
    <div className={s.container}>
      <div className={s.header}>
        <span className={s.planName}>{activeTopic}</span>
        {fsmState && (
          <span className={s.fsmBadge} data-fsm-state={fsmState.toLowerCase()}>{fsmState}</span>
        )}
      </div>

      {convs.length > 0 && (
        <div className={s.progressSection}>
          <div className={s.progressBar}>
            <div className={s.progressFill} style={{ width: `${pct}%` }} />
          </div>
          <div className={s.progressMeta}>
            <span>{doneCount} of {convs.length} done</span>
            <span>{pct}%</span>
          </div>
        </div>
      )}

      <div className={s.cardList}>
        {convs.map((conv, idx) => {
          const isNext = idx === nextConvIdx
          const isFuture = nextConvIdx >= 0 && idx > nextConvIdx && normalizeStatus(conv.status) === undefined
          return (
            <ConvCard
              key={conv.num}
              conv={conv}
              events={events}
              isSelected={selectedConv === conv.num}
              isHovered={hoveredConv === conv.num}
              isNext={isNext}
              isFuture={isFuture}
              onSelect={() => setSelectedConv(conv.num === selectedConv ? null : conv.num)}
              onHoverEnter={() => setHoveredConv(conv.num)}
              onHoverLeave={() => setHoveredConv(null)}
            />
          )
        })}
      </div>

    </div>
  )
}
