import React from 'react'
import type { Stage } from '../types'
import { stageColor } from '../constants'
import s from './StagePill.module.css'

interface Props {
  /** FSM stage ("BUILDING") or a loop marker ("cycle 3"). Empty renders nothing. */
  stage: Stage | string
}

// The FSM stage label. Color comes from the shipped pipeline-state palette via
// `stageColor`, injected as a custom property so the tint/border re-derive from it.
export function StagePill({ stage }: Props): JSX.Element | null {
  if (!stage) return null
  return (
    <span
      className={s.pill}
      style={{ '--stage': stageColor(stage) } as React.CSSProperties}
    >
      {stage}
    </span>
  )
}
