import React from 'react'
import type { EngineCategory, EngineStatus } from '../types'
import { rowControls } from './rowControls'
import s from './EngineRowControls.module.css'

interface Props {
  status: EngineStatus
  category: EngineCategory
  onAction?: (actionId: string) => void
}

// Compact icon control cluster shown per row (revealed on row hover — see EngineRow
// CSS). Verbs are derived from status + category so each engine gets exactly the
// controls that make sense for it.
export function EngineRowControls({ status, category, onAction }: Props): JSX.Element {
  return (
    <span className={s.cluster}>
      {rowControls(status, category).map((c) => (
        <button
          key={c.id}
          type="button"
          className={s.btn}
          data-kind={c.kind}
          title={c.title}
          aria-label={c.title}
          onClick={(e) => { e.stopPropagation(); onAction?.(c.id) }}
        >
          {c.icon}
        </button>
      ))}
    </span>
  )
}
