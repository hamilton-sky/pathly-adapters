import React, { useMemo, useState } from 'react'
import { GripHorizontal, Maximize2, ChevronUp, X } from 'lucide-react'
import type { DockCategoryFilter, DockEngine } from '../types'
import { MAX_SLOTS } from '../constants'
import { DockFilter } from '../DockFilter/DockFilter'
import { EngineRow } from '../EngineRow/EngineRow'
import s from './DockExpanded.module.css'

interface Props {
  engines: DockEngine[]
  /** DB-backed finished runs (history) — rendered as a 'Recent' section below the live rows. */
  recent?: DockEngine[]
  onCollapse: () => void
  onClose: () => void
  /** Promote to the full Monitor panel. */
  onOpenMonitor?: () => void
  onOpenEngine?: (id: string) => void
  onAction?: (engineId: string, actionId: string) => void
  onPauseAll?: () => void
  onManageQueue?: () => void
  /** Whether the spawn queue is paused — shows a badge and flips the footer button to "Resume". */
  paused?: boolean
  onGripPointerDown?: (e: React.PointerEvent) => void
  /** Authoritative queued count from the spawn gate. */
  queuedCount?: number
  /** Rendered between the rows and the footer when "Manage queue" is toggled on. */
  queueSlot?: React.ReactNode
}

// The expanded dock: header (drag / promote / collapse / close), a mini category filter, the
// scrollable engine rows, an optional queue slot (SpawnQueuePanel), and a queue footer. No global
// control bar — each row carries its own contextual controls.
export function DockExpanded({
  engines, recent, onCollapse, onClose, onOpenMonitor, onOpenEngine, onAction,
  onPauseAll, onManageQueue, paused, onGripPointerDown, queuedCount, queueSlot,
}: Props): JSX.Element {
  const [filter, setFilter] = useState<DockCategoryFilter>('all')

  // History rows for runs that are no longer live. Drop any whose id is still in the live list
  // (a run briefly sits in both as its engine exits) AND any duplicate run_id (useRecentSpawns
  // doesn't dedupe like the Monitor's useRecentEngines does) so a row never renders — or keys —
  // twice.
  const recentRows = useMemo(() => {
    const liveIds = new Set(engines.map((e) => e.id))
    const seen = new Set<string>()
    return (recent ?? []).filter((e) => {
      if (liveIds.has(e.id) || seen.has(e.id)) return false
      seen.add(e.id)
      return true
    })
  }, [engines, recent])

  const counts = useMemo(() => {
    // Count live AND recent rows so the filter tabs reflect everything on screen (parity with
    // the full Monitor board, which counts [...engines, ...recent]).
    const all = [...engines, ...recentRows]
    const c: Record<string, number> = { all: all.length }
    for (const e of all) c[e.category] = (c[e.category] ?? 0) + 1
    return c
  }, [engines, recentRows])

  const running = engines.filter((e) => e.status === 'running').length
  const queued = queuedCount ?? engines.filter((e) => e.status === 'queued').length
  const rows = engines.filter((e) => filter === 'all' || e.category === filter)
  const recentFiltered = recentRows.filter((e) => filter === 'all' || e.category === filter)

  return (
    <div className={s.dock}>
      <div className={s.head} onPointerDown={onGripPointerDown}>
        <span className={s.grip} aria-label="Drag">
          <GripHorizontal size={13} />
        </span>
        <span className={s.title}>Engines</span>
        <span className={s.live} />
        <span className={s.liveLabel}>{running} live</span>
        {paused && <span className={s.paused}>paused</span>}
        <span className={s.actions}>
          <button type="button" className={s.icon} title="Open full Monitor" aria-label="Open full Monitor" onClick={onOpenMonitor}>
            <Maximize2 size={13} />
          </button>
          <button type="button" className={s.icon} title="Collapse" aria-label="Collapse" onClick={onCollapse}>
            <ChevronUp size={14} />
          </button>
          <button type="button" className={s.icon} title="Close" aria-label="Close" onClick={onClose}>
            <X size={14} />
          </button>
        </span>
      </div>

      <DockFilter value={filter} onChange={setFilter} counts={counts} />

      <div className={s.rows}>
        {rows.map((e) => (
          <EngineRow key={e.id} engine={e} onOpen={onOpenEngine} onAction={onAction} />
        ))}
        {recentFiltered.length > 0 && <div className={s.recentLabel}>Recent</div>}
        {recentFiltered.map((e) => (
          <EngineRow key={e.id} engine={e} onOpen={onOpenEngine} onAction={onAction} />
        ))}
        {rows.length === 0 && recentFiltered.length === 0 && (
          <div className={s.empty}>No engines in this view</div>
        )}
      </div>

      {queueSlot}

      <div className={s.foot}>
        <span className={s.queue}>{queued} queued · {running} of {MAX_SLOTS} slots</span>
        <span className={s.footActions}>
          <button type="button" className={s.pill} onClick={onPauseAll}>{paused ? 'Resume' : 'Pause all'}</button>
          <button type="button" className={s.pill} onClick={onManageQueue}>Manage queue</button>
        </span>
      </div>
    </div>
  )
}
