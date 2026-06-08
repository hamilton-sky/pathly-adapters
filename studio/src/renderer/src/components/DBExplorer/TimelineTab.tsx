import type { TransitionData } from './dbExplorerData'
import { StatePill } from './StatePill'
import styles from './TimelineTab.module.css'

interface TimelineTabProps {
  transitions: TransitionData[]
}

export function TimelineTab({ transitions }: TimelineTabProps): JSX.Element {
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
        {(['PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'RETRO', 'DONE'] as const).map((s) => (
          <span key={s} className={styles.legendItem}>
            <i className={styles.legendDot} data-state={s} />
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}
