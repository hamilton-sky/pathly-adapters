import React from 'react'
import { Pause, Shuffle, SquareArrowOutUpRight, Square, X, ArrowUp, RefreshCw, SlidersHorizontal, type LucideIcon } from 'lucide-react'
import type { EngineCategory, EngineStatus } from '../types'
import { controlsForEngine, type EngineControl } from './controlsForEngine'
import s from './EngineControls.module.css'

const ICON: Record<string, LucideIcon> = {
  pause:     Pause,
  reroute:   Shuffle,
  open:      SquareArrowOutUpRight,
  configure: SlidersHorizontal,
  abort:     Square,
  stop:      Square,
  cancel:    X,
  up:        ArrowUp,
  rerun:     RefreshCw,
}

interface Props {
  status: EngineStatus
  category: EngineCategory
  onAction?: (actionId: string) => void
}

// Contextual controls for one engine. Lives in the detail modal footer (not on every
// card), so the board stays scannable. Verbs are derived from category + status.
export function EngineControls({ status, category, onAction }: Props): JSX.Element {
  const controls: EngineControl[] = controlsForEngine(status, category)
  return (
    <div className={s.row}>
      <span className={s.label}>Controls</span>
      {controls.map((c) => {
        const Icon = ICON[c.id]
        return (
          <button
            key={c.id}
            type="button"
            className={s.btn}
            data-kind={c.kind}
            onClick={() => onAction?.(c.id)}
          >
            {Icon && <Icon size={13} />}
            {c.label}
          </button>
        )
      })}
    </div>
  )
}
