import React from 'react'
import type { HunkStatus } from '../useDraftDiff'
import { statusBadgeLabel } from '../hunkLabels'
import styles from './StatusBadge.module.css'

const STATUS_CLASS: Record<HunkStatus, string> = {
  added: styles.added,
  removed: styles.removed,
  changed: styles.changed,
  unchanged: '',
}

/** Small uppercase ADDED / REMOVED / CHANGED pill, coloured by status. */
export function StatusBadge({ status }: { status: HunkStatus }) {
  if (status === 'unchanged') return null
  return <span className={`${styles.badge} ${STATUS_CLASS[status]}`}>{statusBadgeLabel(status)}</span>
}
