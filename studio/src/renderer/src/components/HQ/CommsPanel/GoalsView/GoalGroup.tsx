import { useState } from 'react'
import type { Message } from '../../../CommandCenter/types'
import { GoalGroupHeader } from './GoalGroupHeader'
import { TaskCard } from './TaskCard'
import { orderByDeps } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  goal: Message
  tasks: Message[]
  siblings: Message[]
}

// A collapsible goal: header (with executor + Run) followed by its task DAG in
// dependency order.
export function GoalGroup({ goal, tasks, siblings }: Props): JSX.Element {
  const [open, setOpen] = useState(true)
  const ordered = orderByDeps(tasks)
  return (
    <div className={s.group} data-type="goal">
      <GoalGroupHeader goal={goal} tasks={tasks} open={open} onToggle={() => setOpen((o) => !o)} />
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
