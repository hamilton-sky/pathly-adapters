import { Tooltip } from '../../../ui'
import s from './GoalPlanStatus.module.css'

interface Props {
  state: 'idle' | 'planning'
}

// Non-interactive status pill shown on a goal card that has no tasks yet.
// "idle" = not yet planned; "planning" = decompose run in progress.
export function GoalPlanStatus({ state }: Props): JSX.Element {
  if (state === 'planning') {
    return (
      <span className={s.pill} data-state="planning" aria-label="Planning in progress">
        <span className={s.dot} />
        Planning…
      </span>
    )
  }
  return (
    <Tooltip label="Plan this goal from the board's Evaluate control" placement="top">
      <span className={s.pill} data-state="idle" aria-label="Goal not yet planned">
        Not planned
      </span>
    </Tooltip>
  )
}
