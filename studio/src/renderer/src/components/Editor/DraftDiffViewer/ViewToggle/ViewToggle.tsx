import React from 'react'
import { CardsIcon, ListIcon } from '../icons/Icons'
import type { ViewMode } from '../useViewMode'
import styles from './ViewToggle.module.css'

interface Props {
  value: ViewMode
  onChange: (v: ViewMode) => void
}

/** Icon-only segmented control switching the viewer between Cards and List. */
export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className={styles.toggle} role="tablist" aria-label="View">
      <button
        type="button"
        role="tab"
        aria-selected={value === 'cards'}
        aria-label="Cards view"
        title="Cards"
        className={value === 'cards' ? styles.active : ''}
        onClick={() => onChange('cards')}
      >
        <CardsIcon />
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === 'list'}
        aria-label="List view"
        title="List"
        className={value === 'list' ? styles.active : ''}
        onClick={() => onChange('list')}
      >
        <ListIcon />
      </button>
    </div>
  )
}
