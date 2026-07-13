import React from 'react'
import type { EngineStatus } from '../types'
import { statusColor } from '../constants'
import s from './StatusDot.module.css'

interface Props {
  status: EngineStatus
}

// Small live-state dot. Queued blinks (gated on prefers-reduced-motion in CSS);
// running/done/failed are steady.
export function StatusDot({ status }: Props): JSX.Element {
  return (
    <span
      className={s.dot}
      data-status={status}
      style={{ '--dot': statusColor(status) } as React.CSSProperties}
    />
  )
}
