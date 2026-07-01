import { useState } from 'react'
import { ChevronDown, ChevronRight, Trash2, Pencil, Network } from 'lucide-react'
import type { Message } from '../../../types'
import { Tooltip } from '../../../../ui'
import { ConfirmModal } from '../../../../shared/ConfirmModal/ConfirmModal'
import { CopyTextButton } from '../../../../shared/CopyTextButton/CopyTextButton'
import { GoalRunButton } from '../../GoalRunButton/GoalRunButton'
import { GoalPlanStatus } from '../../GoalPlanStatus/GoalPlanStatus'
import { EditableGoalTitle } from './EditableGoalTitle'
import { computeRollup, serializeTasks } from '../../GoalsView/goalsViewUtils'
import { useCommsStore } from '../../../../../store/commsStore'
import s from './GoalCard.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  open: boolean
  onToggle: () => void
  onEditGoal: (goalId: string, text: string) => void
  onDeleteGoal: (goalId: string) => void
  onOpenDetail: () => void
}

// Goal header: collapse toggle + title, then a single right-aligned action group (edit · view-DAG
// · copy-all · delete) — uniform icon buttons that hold their place in view and edit mode. Row 2
// carries the task rollup + executor/Run, or a non-interactive plan-status pill while the goal has
// no tasks yet (planning is launched from the board's Evaluate control, not from the card).
export function GoalCardHeader({ goal, tasks, open, onToggle, onEditGoal, onDeleteGoal, onOpenDetail }: Props): JSX.Element {
  const r = computeRollup(tasks)
  const [confirming, setConfirming] = useState(false)
  const [editing, setEditing] = useState(false)
  const goalRunState = useCommsStore((st) => st.goalRunState)
  // Any non-idle run state (running · busy while board-locked · done during the 3s reload
  // window) reads as "Planning…" so the pill never flashes "Not planned" mid-decompose.
  const isPlanning = (goalRunState[goal.id] ?? 'idle') !== 'idle'
  return (
    <div className={s.header}>
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
        <EditableGoalTitle text={goal.text} editing={editing} onSave={(t) => onEditGoal(goal.id, t)} onCancel={() => setEditing(false)} />
        <div className={s.actions}>
          {!editing && (
            <Tooltip label="Edit goal title" placement="top">
              <button type="button" className={s.actBtn} onClick={() => setEditing(true)} aria-label="Edit goal title">
                <Pencil size={13} />
              </button>
            </Tooltip>
          )}
          {tasks.length > 0 && (
            <Tooltip label="View DAG & details" placement="top">
              <button type="button" className={s.actBtn} onClick={onOpenDetail} aria-label="View DAG and details">
                <Network size={13} />
              </button>
            </Tooltip>
          )}
          {tasks.length > 0 && <CopyTextButton text={serializeTasks(goal.text, tasks)} label="all tasks" />}
          <Tooltip label="Delete goal" placement="top">
            <button type="button" className={s.actBtnDanger} onClick={() => setConfirming(true)} aria-label="Delete goal">
              <Trash2 size={13} />
            </button>
          </Tooltip>
        </div>
      </div>
      <div className={s.metaRow}>
        <span className={s.rollup}>
          {r.total} task{r.total !== 1 ? 's' : ''} · {r.done} done · {r.ready} ready
          {r.failed > 0 ? ` · ${r.failed} blocked` : ''}
        </span>
        <div className={s.controls}>
          {tasks.length > 0
            ? <GoalRunButton goalId={goal.id} defaultExecutor={goal.executor ?? 'single'} />
            : <GoalPlanStatus state={isPlanning ? 'planning' : 'idle'} />}
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
