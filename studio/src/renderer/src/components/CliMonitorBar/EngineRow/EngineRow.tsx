import React from 'react'
import type { DockEngine } from '../types'
import { categoryColor, statusColor, stageColor, ADAPTER_COLOR } from '../constants'
import { EngineRowControls } from '../EngineRowControls/EngineRowControls'
import s from './EngineRow.module.css'

interface Props {
  engine: DockEngine
  onOpen?: (id: string) => void
  onAction?: (engineId: string, actionId: string) => void
}

// A single engine line in the expanded dock. Category accent bar + status dot +
// adapter badge + feature/subline + stage pill + elapsed, with the control cluster
// revealed on hover. Clicking the row opens the full Monitor detail for the engine.
export function EngineRow({ engine: e, onOpen, onAction }: Props): JSX.Element {
  return (
    <div
      className={s.row}
      data-status={e.status}
      onClick={() => onOpen?.(e.id)}
    >
      <span className={s.cat} style={{ '--cat-color': categoryColor(e.category) } as React.CSSProperties} />
      <span className={s.dot} data-status={e.status} style={{ '--dot-color': statusColor(e.status) } as React.CSSProperties} />
      <span
        className={s.adapter}
        style={{ '--adapter': ADAPTER_COLOR[e.adapter] } as React.CSSProperties}
      >
        {e.adapter}
      </span>
      <span className={s.body}>
        <span className={s.feature}>{e.feature}</span>
        <span className={s.sub}>{e.sub}</span>
      </span>
      {e.stage && (
        <span className={s.stage} style={{ '--stage': stageColor(e.stage) } as React.CSSProperties}>
          {e.stage}
        </span>
      )}
      <span className={s.elapsed}>{e.elapsed}</span>
      <EngineRowControls
        status={e.status}
        category={e.category}
        onAction={(actionId) => onAction?.(e.id, actionId)}
      />
    </div>
  )
}
