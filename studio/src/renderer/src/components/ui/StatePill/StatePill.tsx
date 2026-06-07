import clsx from 'clsx'
import styles from './StatePill.module.css'

export type PipelineState = 'PLANNING' | 'BUILDING' | 'REVIEWING' | 'TESTING' | 'RETRO' | 'DONE' | 'ERROR' | 'IDLE'

interface StatePillProps {
  state?: PipelineState
  /** Override visible text */
  label?: string
  /** Solid fill instead of tint (high-emphasis) */
  solid?: boolean
  className?: string
}

export function StatePill({ state = 'PLANNING', label, solid = false, className }: StatePillProps) {
  const key = state.toUpperCase() as PipelineState
  return (
    <span
      className={clsx(styles.pill, solid && styles.solid, className)}
      data-state={key}
    >
      <span className={styles.dot} />
      {label ?? key}
    </span>
  )
}
