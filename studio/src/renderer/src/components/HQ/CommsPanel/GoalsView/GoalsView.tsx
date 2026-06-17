import { Target } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { GoalGroup } from './GoalGroup'
import { TaskCard } from './TaskCard'
import { orderByDeps } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  messages: Message[]
}

// The "Goals & Tasks" board view: each goal renders as a group with its task DAG
// nested beneath. Tasks are linked to a goal by goal_id; any task without a known
// goal falls into an "Ungrouped tasks" section.
export function GoalsView({ messages }: Props): JSX.Element {
  const goals = messages.filter((m) => m.type === 'goal')
  const goalIds = new Set(goals.map((g) => g.id))

  const tasksByGoal = new Map<string, Message[]>()
  const ungrouped: Message[] = []
  for (const m of messages) {
    if (m.type !== 'task') continue
    if (m.goal_id && goalIds.has(m.goal_id)) {
      const arr = tasksByGoal.get(m.goal_id) ?? []
      arr.push(m)
      tasksByGoal.set(m.goal_id, arr)
    } else {
      ungrouped.push(m)
    }
  }

  if (goals.length === 0 && ungrouped.length === 0) {
    return (
      <div className={s.empty}>
        <Target size={22} />
        <p>No goals on this board yet. The planner seeds a goal and its task DAG.</p>
      </div>
    )
  }

  return (
    <div className={s.view}>
      {goals.map((g) => (
        <GoalGroup key={g.id} goal={g} tasks={tasksByGoal.get(g.id) ?? []} siblings={messages} />
      ))}
      {ungrouped.length > 0 && (
        <div className={s.ungrouped}>
          <div className={s.ungroupedHead}>Ungrouped tasks</div>
          {orderByDeps(ungrouped).map((t) => (
            <TaskCard key={t.id} task={t} siblings={messages} />
          ))}
        </div>
      )}
    </div>
  )
}
