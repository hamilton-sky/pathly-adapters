import React from 'react'
import type { DiffHunk } from '../useDraftDiff'
import { acceptChipLabel } from '../hunkLabels'
import styles from './AcceptToggleChip.module.css'

interface Props {
  hunk: DiffHunk
  onToggle: (id: string) => void
}

/** Pill that flips a hunk between its draft and original choice.
 *  Stops click propagation so it works inside a clickable card/row. */
export function AcceptToggleChip({ hunk, onToggle }: Props) {
  return (
    <button
      type="button"
      className={`${styles.chip} ${hunk.accepted ? styles.accepted : ''}`}
      onClick={(e) => {
        e.stopPropagation()
        onToggle(hunk.id)
      }}
    >
      {acceptChipLabel(hunk)}
    </button>
  )
}
