import type { PipelineState } from '../dbExplorerData'
import styles from './StatePill.module.css'

interface StatePillProps {
  state: PipelineState
}

export function StatePill({ state }: StatePillProps): JSX.Element {
  return (
    <span className={styles.pill} data-state={state}>
      <span className={styles.dot} />
      {state}
    </span>
  )
}
