import { useState } from 'react'
import type { Message } from '../../../types'
import { GoalCardHeader } from './GoalCardHeader'
import { TaskCard } from '../TaskCard/TaskCard'
import { orderByDeps } from '../../GoalsView/goalsViewUtils'
import s from './GoalCard.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  siblings: Message[]
  onEditGoal: (goalId: string, text: string) => void
  onDeleteGoal: (goalId: string) => void
}

// A collapsible goal: header (with executor + Run) followed by its task DAG in
// dependency order.
export function GoalCard({ goal, tasks, siblings, onEditGoal, onDeleteGoal }: Props): JSX.Element {
  const [open, setOpen] = useState(true)
  const ordered = orderByDeps(tasks)
  return (
    <div className={s.group} data-type="goal">
      <GoalCardHeader goal={goal} tasks={tasks} open={open} onToggle={() => setOpen((o) => !o)} onEditGoal={onEditGoal} onDeleteGoal={onDeleteGoal} />
      {open && (
        <div className={s.tasks}>
          {ordered.length > 0
            ? ordered.map((t) => <TaskCard key={t.id} task={t} siblings={siblings} />)
            : <div className={s.noTasks}>No tasks decomposed yet.</div>}
        </div>
      )}
    </div>
  )
}
