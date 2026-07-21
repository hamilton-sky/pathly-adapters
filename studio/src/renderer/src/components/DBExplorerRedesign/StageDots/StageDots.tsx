import type { DotSegment } from '../types'
import styles from './StageDots.module.css'

interface StageDotsProps {
  dots: DotSegment[]
  /** Thinner bars for the preview popover. */
  compact?: boolean
}

/**
 * The stage-history strip shown on each feature card: one segment per stage
 * the feature passed through, coloured by FSM state. This is a *summary* of the
 * feature flow — not a live flow graph and not a kanban board.
 */
export function StageDots({ dots, compact = false }: StageDotsProps): JSX.Element {
  return (
    <div className={`${styles.dots} ${compact ? styles.compact : ''}`}>
      {dots.map((d, i) => (
        <div
          key={i}
          className={styles.segment}
          data-state={d.state}
          style={{ ['--seg-flex' as string]: d.flex ?? 1 }}
        />
      ))}
    </div>
  )
}
