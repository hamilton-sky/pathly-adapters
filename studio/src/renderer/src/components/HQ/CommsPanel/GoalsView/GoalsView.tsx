import { Target } from 'lucide-react'
import type { Message } from '../../../CommandCenter/types'
import { GoalGroup } from './GoalGroup'
import { TaskCard } from './TaskCard'
import { NewGoalButton } from './NewGoalButton'
import { orderByDeps } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  messages: Message[]
  onCreateGoal: (text: string) => void
  onEditGoal: (goalId: string, text: string) => void
}

// The "Goals & Tasks" board view: each goal renders as a group with its task DAG
// nested beneath. Tasks are linked to a goal by goal_id; any task without a known
// goal falls into an "Ungrouped tasks" section. A "+ New goal" control lets the
// human seed a goal directly (it then offers Decompose → Run).
export function GoalsView({ messages, onCreateGoal, onEditGoal }: Props): JSX.Element {
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
        <p>No goals on this board yet. Add one below, or let the planner seed a goal and its task DAG.</p>
        <NewGoalButton onCreate={onCreateGoal} />
      </div>
    )
  }

  return (
    <div className={s.view}>
      <div className={s.viewHeader}>
        <NewGoalButton onCreate={onCreateGoal} />
      </div>
      {goals.map((g) => (
        <GoalGroup key={g.id} goal={g} tasks={tasksByGoal.get(g.id) ?? []} siblings={messages} onEditGoal={onEditGoal} />
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
