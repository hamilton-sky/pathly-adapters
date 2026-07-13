import React from 'react'
import type { DockCategoryFilter } from '../types'
import { categoryColor } from '../constants'
import s from './DockFilter.module.css'

interface Props {
  value: DockCategoryFilter
  onChange: (v: DockCategoryFilter) => void
  counts: Record<string, number>
}

const SEGMENTS: { key: DockCategoryFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'flow', label: 'Flow' },
  { key: 'loop', label: 'Loop' },
  { key: 'single', label: 'Single' },
]

// Mini category filter inside the expanded dock — mirrors the full Monitor's
// CategoryFilterBar so the two surfaces read the same.
export function DockFilter({ value, onChange, counts }: Props): JSX.Element {
  return (
    <div className={s.bar}>
      {SEGMENTS.map((seg) => (
        <button
          key={seg.key}
          type="button"
          className={s.seg}
          {...(value === seg.key ? { 'data-active': '' } : {})}
          onClick={() => onChange(seg.key)}
        >
          {seg.key !== 'all' && (
            <span className={s.dot} style={{ '--seg-dot': categoryColor(seg.key as never) } as React.CSSProperties} />
          )}
          {seg.label}
          <span className={s.count}>{counts[seg.key] ?? 0}</span>
        </button>
      ))}
    </div>
  )
}
