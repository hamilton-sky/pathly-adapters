import React from 'react'
import type { MonitorEngine } from '../types'
import type { CategoryMeta } from '../constants'
import { EngineCard } from '../EngineCard/EngineCard'
import s from './EngineSection.module.css'

interface Props {
  meta: CategoryMeta
  engines: MonitorEngine[]
  onOpen?: (id: string) => void
  onAction?: (engineId: string, actionId: string) => void
}

// One category band: colored heading dot + Title-Case label + muted blurb + count
// badge, then a responsive grid of engine cards. Renders nothing when empty so the
// board only shows categories that actually have engines.
export function EngineSection({ meta, engines, onOpen, onAction }: Props): JSX.Element | null {
  if (engines.length === 0) return null
  return (
    <section className={s.section}>
      <div className={s.header}>
        <span className={s.dot} style={{ '--section-dot': meta.color } as React.CSSProperties} />
        <span className={s.label}>{meta.label}</span>
        <span className={s.blurb}>{meta.blurb}</span>
        <span className={s.count}>{engines.length}</span>
      </div>
      <div className={s.grid}>
        {engines.map((e) => (
          <EngineCard key={e.id} engine={e} onOpen={onOpen} onAction={onAction} />
        ))}
      </div>
    </section>
  )
}
