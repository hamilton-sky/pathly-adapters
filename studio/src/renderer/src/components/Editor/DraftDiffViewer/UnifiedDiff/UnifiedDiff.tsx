import React from 'react'
import type { UnifiedRow } from '../fileDiffUtils'
import styles from './UnifiedDiff.module.css'

const ROW_CLASS: Record<string, string> = {
  remove: styles.remove,
  add: styles.add,
  same: '',
}

/** Inline single-column file diff with a dual line-number gutter. */
export function UnifiedDiff({ rows }: { rows: UnifiedRow[] }) {
  return (
    <div className={styles.uni}>
      {rows.map((r, i) => (
        <div className={`${styles.row} ${ROW_CLASS[r.type]}`} key={i}>
          <span className={styles.ln}>{r.originalNo ?? ''}</span>
          <span className={styles.ln}>{r.draftNo ?? ''}</span>
          <span className={styles.sign}>{r.type === 'remove' ? '−' : r.type === 'add' ? '+' : ' '}</span>
          <span className={styles.tx}>{r.text || ' '}</span>
        </div>
      ))}
    </div>
  )
}
