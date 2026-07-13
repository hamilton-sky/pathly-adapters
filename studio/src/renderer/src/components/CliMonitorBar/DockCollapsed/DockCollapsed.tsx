import React from 'react'
import { GripHorizontal, ChevronDown, X } from 'lucide-react'
import type { DockEngine } from '../types'
import { CATEGORY_ORDER, categoryColor } from '../constants'
import s from './DockCollapsed.module.css'

interface Props {
  engines: DockEngine[]
  onExpand: () => void
  /** Dismiss the dock entirely (the host re-shows it via its own affordance). */
  onClose?: () => void
  /** Optional drag handle wiring (pointer-down starts the drag in the host). */
  onGripPointerDown?: (e: React.PointerEvent) => void
}

// The glanceable collapsed pill: drag handle, live count, per-category tallies, and a thin load
// strip showing the running/queued mix. One click expands.
export function DockCollapsed({ engines, onExpand, onClose, onGripPointerDown }: Props): JSX.Element {
  const running = engines.filter((e) => e.status === 'running').length
  const counts: Record<string, number> = {}
  for (const e of engines) counts[e.category] = (counts[e.category] ?? 0) + 1

  return (
    <div className={s.dock}>
      <div className={s.head} onPointerDown={onGripPointerDown}>
        <span className={s.grip} aria-label="Drag">
          <GripHorizontal size={13} />
        </span>
        <span className={s.title}>Engines</span>
        <span className={s.live} />
        <span className={s.liveLabel}>{running} live</span>
        <span className={s.tallies}>
          {CATEGORY_ORDER.map((cat) => (
            <span key={cat} className={s.tally}>
              <span className={s.tallyDot} style={{ '--tally-dot': categoryColor(cat) } as React.CSSProperties} />
              {counts[cat] ?? 0}
            </span>
          ))}
          <button type="button" className={s.icon} onClick={onExpand} aria-label="Expand" title="Expand">
            <ChevronDown size={14} />
          </button>
          {onClose && (
            <button type="button" className={s.icon} onClick={onClose} aria-label="Close" title="Close">
              <X size={12} />
            </button>
          )}
        </span>
      </div>
      <div className={s.strip}>
        {engines.map((e) => (
          <span
            key={e.id}
            className={s.bar}
            style={{ '--bar-color': e.status === 'queued' ? 'var(--text-muted)' : categoryColor(e.category) } as React.CSSProperties}
          />
        ))}
      </div>
    </div>
  )
}
