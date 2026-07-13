import React from 'react'
import type { EngineCategory } from '../types'
import s from './CategoryBadge.module.css'

interface Props {
  category: EngineCategory
}

// Tinted uppercase mono label classifying how the engine runs. The tint is driven
// by `data-cat` in CSS (color-mix from the category color) — never inlined.
export function CategoryBadge({ category }: Props): JSX.Element {
  return (
    <span className={s.badge} data-cat={category}>
      {category}
    </span>
  )
}
