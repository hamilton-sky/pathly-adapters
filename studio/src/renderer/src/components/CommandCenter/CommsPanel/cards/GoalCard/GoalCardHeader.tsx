import { useState } from 'react'
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import { ConfirmModal } from '../../../../shared/ConfirmModal/ConfirmModal'
import { GoalRunButton } from '../../GoalRunButton/GoalRunButton'
import { GoalDecomposeButton } from '../../GoalDecomposeButton/GoalDecomposeButton'
import { EditableGoalTitle } from './EditableGoalTitle'
import { computeRollup } from '../../GoalsView/goalsViewUtils'
import s from './GoalCard.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  open: boolean
  onToggle: () => void
  onEditGoal: (goalId: string, text: string) => void
  onDeleteGoal: (goalId: string) => void
}

// Goal header: collapse toggle + goal text + a task rollup chip + the executor
// selector / Run control (reused from GoalRunButton — the selector value is sent
// as the executor override on Run, which persists it onto the goal) + a delete
// affordance (mirrors the message card's trash → confirm → remove).
export function GoalCardHeader({ goal, tasks, open, onToggle, onEditGoal, onDeleteGoal }: Props): JSX.Element {
  const r = computeRollup(tasks)
  const [confirming, setConfirming] = useState(false)
  return (
    <div className={s.header}>
      {/* Row 1 — collapse + title (full width) + delete */}
      <div className={s.titleRow}>
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
        <EditableGoalTitle text={goal.text} onSave={(t) => onEditGoal(goal.id, t)} />
        <Tooltip label="Delete goal" placement="top">
          <button
            type="button"
            className={s.goalDel}
            aria-label="Delete goal"
            onClick={() => setConfirming(true)}
          >
            <Trash2 size={13} />
          </button>
        </Tooltip>
      </div>
      {/* Row 2 — task rollup + executor/Run controls (wrap, never crush the title) */}
      <div className={s.metaRow}>
        <span className={s.rollup}>
          {r.total} task{r.total !== 1 ? 's' : ''} · {r.done} done · {r.ready} ready
          {r.failed > 0 ? ` · ${r.failed} blocked` : ''}
        </span>
        <div className={s.controls}>
          {/* No tasks yet → Decompose the goal into a DAG; once it has tasks → Run it. */}
          {tasks.length === 0
            ? <GoalDecomposeButton goalId={goal.id} goalText={goal.text} />
            : <GoalRunButton goalId={goal.id} defaultExecutor={goal.executor ?? 'single'} />}
        </div>
      </div>
      {confirming && (
        <ConfirmModal
          title="Delete this goal?"
          message={tasks.length > 0
            ? `This goal has ${tasks.length} task${tasks.length === 1 ? '' : 's'}. The goal is removed from the board; its tasks become ungrouped.`
            : 'It will be removed from the board and its memory.'}
          onCancel={() => setConfirming(false)}
          onConfirm={() => { setConfirming(false); onDeleteGoal(goal.id) }}
        />
      )}
    </div>
  )
}
