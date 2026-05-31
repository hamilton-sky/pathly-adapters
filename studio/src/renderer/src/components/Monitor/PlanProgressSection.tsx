import { useState, useEffect, useRef } from 'react'
import { usePlanConversations } from '../../hooks/usePlanConversations'
import styles from './Monitor.module.css'

interface Props {
  topic: string | null
}

export function PlanProgressSection({ topic }: Props): JSX.Element | null {
  const [open, setOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const fillRef = useRef<HTMLDivElement>(null)
  const { planConvs } = usePlanConversations(topic)

  const total = planConvs.length
  const doneCount = planConvs.filter((c) => c.status === 'DONE').length
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0

  // Set aria-expanded imperatively to avoid JSX expression lint false-positive
  useEffect(() => {
    buttonRef.current?.setAttribute('aria-expanded', String(open))
  }, [open])

  // Set fill width imperatively to avoid JSX inline style lint warning
  useEffect(() => {
    if (fillRef.current) fillRef.current.style.width = `${pct}%`
  }, [pct])

  if (planConvs.length === 0) return null

  return (
    <div className={styles.convSection}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
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
        <div ref={fillRef} className={styles.convProgressFill} />
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
