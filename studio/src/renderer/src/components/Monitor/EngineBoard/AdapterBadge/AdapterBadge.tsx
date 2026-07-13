import React from 'react'
import type { EngineAdapter } from '../types'
import { ADAPTER_COLOR } from '../constants'
import s from './AdapterBadge.module.css'

interface Props {
  adapter: EngineAdapter
}

// Which host CLI is driving the engine. The adapter accent is a host brand color,
// so it's passed as a CSS custom property rather than a token.
export function AdapterBadge({ adapter }: Props): JSX.Element {
  return (
    <span
      className={s.badge}
      style={{ '--adapter': ADAPTER_COLOR[adapter] } as React.CSSProperties}
    >
      {adapter}
    </span>
  )
}
