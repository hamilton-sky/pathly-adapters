import React from 'react'
import { ChevronRight } from 'lucide-react'
import type { MonitorEngine } from '../types'
import { CategoryBadge } from '../CategoryBadge/CategoryBadge'
import { AdapterBadge } from '../AdapterBadge/AdapterBadge'
import { StagePill } from '../StagePill/StagePill'
import { StatusDot } from '../StatusDot/StatusDot'
import s from './EngineCard.module.css'

interface Props {
  engine: MonitorEngine
  onOpen?: (id: string) => void
}

// A clickable ticket for one CLI engine — the board's atomic unit. Carries the
// engine's metadata (category, adapter, role, stage, tokens, cost, latest output).
// Clicking opens the detail modal, where the contextual controls live.
export function EngineCard({ engine: e, onOpen }: Props): JSX.Element {
  const queued = e.status === 'queued'
  return (
    <button
      type="button"
      className={s.card}
      {...(queued ? { 'data-queued': '' } : {})}
      onClick={() => onOpen?.(e.id)}
    >
      <div className={s.head}>
        <CategoryBadge category={e.category} />
        <AdapterBadge adapter={e.adapter} />
        <span className={s.status}>
          <StatusDot status={e.status} />
          <span className={s.elapsed}>{e.elapsed}</span>
        </span>
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
    </button>
  )
}
