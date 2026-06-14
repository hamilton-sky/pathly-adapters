import React from 'react'
import { CardsIcon, ListIcon, CodeDiffIcon, EditIcon } from '../icons/Icons'
import type { ViewMode } from '../useViewMode'
import styles from './ViewToggle.module.css'

interface Props {
  value: ViewMode
  onChange: (v: ViewMode) => void
}

/** Icon-only segmented control switching the viewer between Cards, List, Code and Edit. */
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
      <button
        type="button"
        role="tab"
        aria-selected={value === 'code'}
        aria-label="Code diff view"
        title="Code diff"
        className={value === 'code' ? styles.active : ''}
        onClick={() => onChange('code')}
      >
        <CodeDiffIcon />
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === 'edit'}
        aria-label="Edit result view"
        title="Edit result"
        className={value === 'edit' ? styles.active : ''}
        onClick={() => onChange('edit')}
      >
        <EditIcon />
      </button>
    </div>
  )
}
