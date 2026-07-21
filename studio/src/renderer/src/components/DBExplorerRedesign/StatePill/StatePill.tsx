import type { PipelineState } from '../types'
import styles from './StatePill.module.css'

interface StatePillProps {
  state: PipelineState
  /** Slightly larger padding for the detail-page header. */
  large?: boolean
}

/** The FSM-stage pill — coloured dot + uppercase state label. */
export function StatePill({ state, large = false }: StatePillProps): JSX.Element {
  return (
    <span className={`${styles.pill} ${large ? styles.large : ''}`} data-state={state}>
      <span className={styles.dot} />
      {state}
    </span>
  )
}
