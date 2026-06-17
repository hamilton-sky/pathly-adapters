import { ChevronDown, ChevronRight } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import MarkdownRenderer from '../../../../components/shared/MarkdownRenderer/MarkdownRenderer'
import { GoalRunButton } from '../GoalRunButton/GoalRunButton'
import { GoalDecomposeButton } from '../GoalDecomposeButton/GoalDecomposeButton'
import { computeRollup } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  open: boolean
  onToggle: () => void
}

// Goal header: collapse toggle + goal text + a task rollup chip + the executor
// selector / Run control (reused from GoalRunButton — the selector value is sent
// as the executor override on Run, which persists it onto the goal).
export function GoalGroupHeader({ goal, tasks, open, onToggle }: Props): JSX.Element {
  const r = computeRollup(tasks)
  return (
    <div className={s.header}>
      <button
        type="button"
        className={s.collapse}
        onClick={onToggle}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        aria-label={open ? 'Collapse goal' : 'Expand goal'}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      <div className={s.headerMain}>
        <MarkdownRenderer content={goal.text} className={s.goalText} />
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
