import React from 'react'
import { ChevronRight, Square, X } from 'lucide-react'
import type { MonitorEngine } from '../types'
import { CategoryBadge } from '../CategoryBadge/CategoryBadge'
import { AdapterBadge } from '../AdapterBadge/AdapterBadge'
import { StagePill } from '../StagePill/StagePill'
import { StatusDot } from '../StatusDot/StatusDot'
import s from './EngineCard.module.css'

interface Props {
  engine: MonitorEngine
  view?: 'grid' | 'banner'
  onOpen?: (id: string) => void
  onAction?: (engineId: string, actionId: string) => void
}

// A clickable ticket for one CLI engine — the board's atomic unit. Clicking (or Enter/Space) opens
// the detail modal with the full contextual controls; a quick Stop (running) / Cancel (queued)
// button sits on the card itself so the common action doesn't require opening the modal first.
export function EngineCard({ engine: e, view = 'grid', onOpen, onAction }: Props): JSX.Element {
  const queued = e.status === 'queued'
  const running = e.status === 'running'
  return (
    <div
      className={s.card}
      role="button"
      tabIndex={0}
      data-view={view}
      {...(queued ? { 'data-queued': '' } : {})}
      onClick={() => onOpen?.(e.id)}
      onKeyDown={(ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault()
          onOpen?.(e.id)
        }
      }}
    >
      <div className={s.head}>
        <CategoryBadge category={e.category} />
        <AdapterBadge adapter={e.adapter} />
        <span className={s.status}>
          <StatusDot status={e.status} />
          <span className={s.elapsed}>{e.elapsed}</span>
        </span>
        {running && onAction && (
          <button
            type="button"
            className={s.stop}
            title="Stop engine"
            aria-label="Stop engine"
            onClick={(ev) => { ev.stopPropagation(); onAction(e.id, 'stop') }}
          >
            <Square size={12} />
          </button>
        )}
        {queued && onAction && (
          <button
            type="button"
            className={s.stop}
            title="Cancel queued run"
            aria-label="Cancel queued run"
            onClick={(ev) => { ev.stopPropagation(); onAction(e.id, 'cancel') }}
          >
            <X size={13} />
          </button>
        )}
      </div>

      <div className={s.feature}>{e.feature}</div>
      <div className={s.snippet}>{e.snippet}</div>

      <div className={s.foot}>
        <StagePill stage={e.stage} />
        <span className={s.role}>{e.role}</span>
        <span className={s.metrics}>
          <span className={s.tokens}>{e.tokens}</span>
          <span className={s.cost} data-empty={e.cost === '-'}>{e.cost}</span>
          <span className={s.details}>Details <ChevronRight size={12} /></span>
        </span>
      </div>
    </div>
  )
}
