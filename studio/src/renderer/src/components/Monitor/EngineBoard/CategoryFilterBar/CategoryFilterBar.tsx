import React from 'react'
import type { EngineAdapter, EngineCategory } from '../types'
import { CATEGORY_META, ADAPTERS, ADAPTER_COLOR } from '../constants'
import s from './CategoryFilterBar.module.css'

/** 'all' plus the three categories. */
export type CategoryFilter = 'all' | EngineCategory

interface Props {
  category: CategoryFilter
  onCategory: (c: CategoryFilter) => void
  /** null = all adapters. */
  adapter: EngineAdapter | null
  onAdapter: (a: EngineAdapter | null) => void
  /** Per-category counts, e.g. { all: 8, flow: 4, loop: 1, single: 3 }. */
  counts: Record<string, number>
}

// The top segmented bar — mirrors the Command Center board tab bar. Left: category
// segments (All / Flow / Loop / Single) with live counts. Right: adapter chips that
// filter by engine. Clicking an active adapter chip clears it.
export function CategoryFilterBar({ category, onCategory, adapter, onAdapter, counts }: Props): JSX.Element {
  const segments: { key: CategoryFilter; label: string; color?: string }[] = [
    { key: 'all', label: 'All' },
    ...CATEGORY_META.map((c) => ({ key: c.key, label: c.label.split(' ')[0], color: c.color })),
  ]

  return (
    <div className={s.bar}>
      {segments.map((seg) => (
        <button
          key={seg.key}
          type="button"
          className={s.seg}
          {...(category === seg.key ? { 'data-active': '' } : {})}
          onClick={() => onCategory(seg.key)}
        >
          {seg.color && <span className={s.segDot} style={{ '--seg-dot': seg.color } as React.CSSProperties} />}
          {seg.label}
          <span className={s.segCount}>{counts[seg.key] ?? 0}</span>
        </button>
      ))}

      <div className={s.adapters}>
        <span className={s.adaptersLabel}>Engine</span>
        {ADAPTERS.map((a) => (
          <button
            key={a}
            type="button"
            className={s.chip}
            style={{ '--adapter': ADAPTER_COLOR[a] } as React.CSSProperties}
            {...(adapter === a ? { 'data-active': '' } : {})}
            onClick={() => onAdapter(adapter === a ? null : a)}
          >
            <span className={s.chipDot} />
            {a}
          </button>
        ))}
      </div>
    </div>
  )
}
