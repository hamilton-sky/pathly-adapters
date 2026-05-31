import React, { useState } from 'react'
import { usePlanConversations } from '../../hooks/usePlanConversations'
import styles from './Monitor.module.css'

interface Props {
  topic: string | null
}

export function PlanProgressSection({ topic }: Props): JSX.Element | null {
  const [open, setOpen] = useState(false)
  const { planConvs } = usePlanConversations(topic)

  if (planConvs.length === 0) return null

  const total = planConvs.length
  const doneCount = planConvs.filter((c) => c.status === 'DONE').length
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  return (
    <div className={styles.convSection}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open ? "true" : "false"}
        className={styles.convToggleBtn}
      >
        <span className={styles.convLabel}>Conversations</span>
        <span className={styles.convRight}>
          <span className={`${styles.convCount} ${doneCount === total ? styles.convCountDone : styles.convCountPending}`}>
            {doneCount}/{total}
          </span>
          <span className={`${styles.convChevron} ${open ? styles.convChevronOpen : ''}`}>▾</span>
        </span>
      </button>

      <div className={styles.convProgressTrack}>
        <div className={styles.convProgressFill} style={{ width: `${pct}%` }} />
      </div>

      {open && (
        <div className={styles.convList}>
          {planConvs.map((conv) => {
            const done = conv.status === 'DONE'
            return (
              <div key={conv.num} className={styles.convRow}>
                <span className={`${styles.convCircle} ${done ? styles.convCircleDone : styles.convCircleTodo}`}>
                  {done ? '✓' : String(conv.num)}
                </span>
                <span className={styles.convTitle}>{conv.title || `Conv ${conv.num}`}</span>
                <span className={`${styles.convBadge} ${done ? styles.convBadgeDone : styles.convBadgeTodo}`}>
                  {done ? 'done' : 'todo'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
