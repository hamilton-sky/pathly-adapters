import type { PlanState } from '../types'
import { STATE_COLOR } from '../lib/kinds'
import styles from './StatePill.module.css'

interface Props {
  state: PlanState
}

/** Small lifecycle badge shown on plan folders. */
export function StatePill({ state }: Props): JSX.Element {
  const color = STATE_COLOR[state]
  return (
    <span
      className={styles.pill}
      style={{
        color,
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
      }}
    >
      {state}
    </span>
  )
}
