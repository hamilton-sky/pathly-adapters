import type { TransitionData } from '../dbExplorerData'
import { StatePill } from '../StatePill'
import styles from './TimelineTab.module.css'

interface TimelineTabProps {
  transitions: TransitionData[]
}

export function TimelineTab({ transitions }: TimelineTabProps): JSX.Element {
  // A feature can reach its state without the FSM ever stepping through the pipeline —
  // goal/loop runs do the work but don't advance the feature-level state machine, so no
  // STATE_TRANSITION events exist. Show that plainly instead of a blank timeline under a
  // fixed legend that implies stages (e.g. REVIEWING/TESTING) which never actually ran.
  if (transitions.length === 0) {
    return (
      <div>
        <p className={styles.sublabel}>State Machine Transitions</p>
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No state transitions recorded</p>
          <p className={styles.emptyBody}>
            This feature reached its current state without the FSM stepping through the
            pipeline — its work ran via goal or loop runs, which don&apos;t advance the
            feature-level state machine. See the <strong>Agents</strong> and{' '}
            <strong>Events</strong> tabs for what actually ran.
          </p>
        </div>
      </div>
    )
  }

  // Legend reflects only the states that ACTUALLY occurred (in order of first appearance),
  // never a fixed list — so it can't imply a stage that never ran.
  const seenStates = transitions.reduce<TransitionData['state'][]>((acc, t) => {
    if (!acc.includes(t.state)) acc.push(t.state)
    return acc
  }, [])

  return (
    <div>
      <p className={styles.sublabel}>State Machine Transitions</p>
      <div className={styles.timeline}>
        {transitions.map((t, i) => (
          <div key={i} className={styles.stepGroup}>
            <div className={styles.tstep}>
              <StatePill state={t.state} />
              <span className={styles.tstamp}>{t.time}</span>
              <span className={styles.tdur}>{t.duration}</span>
            </div>
            {i < transitions.length - 1 && (
              <span className={styles.tarrow}>›</span>
            )}
          </div>
        ))}
      </div>
      <div className={styles.legend}>
        {seenStates.map((s) => (
          <span key={s} className={styles.legendItem}>
            <i className={styles.legendDot} data-state={s} />
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}
