import styles from './StatePill.module.css'
import type { StageName } from '../../types'

interface StatePillProps {
  state: StageName
  /** Override the displayed text (defaults to the state name). */
  label?: string
}

const STATE_CLASS: Record<string, string> = {
  STORMING: styles.planning,
  PLANNING: styles.planning,
  BUILDING: styles.building,
  REVIEWING: styles.reviewing,
  TESTING: styles.testing,
  DONE: styles.done,
}

/** Small status pill coloured by pipeline state (BUILDING, TESTING, …). */
export function StatePill({ state, label }: StatePillProps): JSX.Element {
  return (
    <span className={`${styles.pill} ${STATE_CLASS[state] ?? styles.building}`}>
      <span className={styles.dot} />
      {label ?? state}
    </span>
  )
}
