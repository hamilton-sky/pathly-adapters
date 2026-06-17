import { ChevronDown, ChevronRight } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { Tooltip } from '../../../ui'
import { GoalRunButton } from '../GoalRunButton/GoalRunButton'
import { GoalDecomposeButton } from '../GoalDecomposeButton/GoalDecomposeButton'
import { EditableGoalTitle } from './EditableGoalTitle'
import { computeRollup } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  open: boolean
  onToggle: () => void
  onEditGoal: (goalId: string, text: string) => void
}

// Goal header: collapse toggle + goal text + a task rollup chip + the executor
// selector / Run control (reused from GoalRunButton — the selector value is sent
// as the executor override on Run, which persists it onto the goal).
export function GoalGroupHeader({ goal, tasks, open, onToggle, onEditGoal }: Props): JSX.Element {
  const r = computeRollup(tasks)
  return (
    <div className={s.header}>
      <Tooltip label={open ? 'Collapse goal' : 'Expand goal'} placement="top">
        <button
          type="button"
          className={s.collapse}
          onClick={onToggle}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
          aria-label={open ? 'Collapse goal' : 'Expand goal'}
        >
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </Tooltip>
      <div className={s.headerMain}>
        <EditableGoalTitle text={goal.text} onSave={(t) => onEditGoal(goal.id, t)} />
        <div className={s.rollup}>
          {r.total} task{r.total !== 1 ? 's' : ''} · {r.done} done · {r.ready} ready
          {r.failed > 0 ? ` · ${r.failed} blocked` : ''}
        </div>
      </div>
      {/* No tasks yet → Decompose the goal into a DAG; once it has tasks → Run it. */}
      {tasks.length === 0
        ? <GoalDecomposeButton goalId={goal.id} />
        : <GoalRunButton goalId={goal.id} defaultExecutor={goal.executor ?? 'single'} />}
    </div>
  )
}
