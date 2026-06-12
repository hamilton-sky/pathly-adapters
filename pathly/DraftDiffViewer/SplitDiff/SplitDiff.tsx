import React from 'react'
import type { SplitRow } from '../fileDiffUtils'
import styles from './SplitDiff.module.css'

const CELL_CLASS: Record<string, string> = {
  remove: styles.remove,
  add: styles.add,
  fill: styles.fill,
  same: '',
}

/** Side-by-side file diff: original left, draft right, changed blocks aligned. */
export function SplitDiff({ rows }: { rows: SplitRow[] }) {
  return (
    <div className={styles.split}>
      {rows.map((r, i) => (
        <div className={styles.row} key={i}>
          <div className={`${styles.cell} ${CELL_CLASS[r.leftType]}`}>
            <span className={styles.ln}>{r.leftNo ?? ''}</span>
            <span className={styles.sign}>{r.leftType === 'remove' ? '−' : ' '}</span>
            <span className={styles.tx}>{r.leftText != null ? r.leftText || ' ' : ''}</span>
          </div>
          <div className={`${styles.cell} ${CELL_CLASS[r.rightType]}`}>
            <span className={styles.ln}>{r.rightNo ?? ''}</span>
            <span className={styles.sign}>{r.rightType === 'add' ? '+' : ' '}</span>
            <span className={styles.tx}>{r.rightText != null ? r.rightText || ' ' : ''}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
