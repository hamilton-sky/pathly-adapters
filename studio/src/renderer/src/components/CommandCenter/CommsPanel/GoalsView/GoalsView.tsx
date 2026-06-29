import { useState } from 'react'
import { Target, Network } from 'lucide-react'
import type { BoardScope, Message } from '../../types'
import { GoalCard } from '../cards/GoalCard/GoalCard'
import { TaskCard } from '../cards/TaskCard/TaskCard'
import { GoalDetailModal } from '../GoalDetailModal/GoalDetailModal'
import { orderByDeps } from './goalsViewUtils'
import s from './GoalsView.module.css'

interface Props {
  messages: Message[]
  boardKey: string
  boardScope: BoardScope
  onEditGoal: (goalId: string, text: string) => void
  onDeleteGoal: (goalId: string) => void
}

// The "Goals & Tasks" board view: each goal renders as a group with its task DAG
// nested beneath. Tasks are linked to a goal by goal_id; any task without a known
// goal falls into an "Ungrouped tasks" section. The "+ New goal" control lives in
// the board's view-toggle row (top right).
export function GoalsView({ messages, boardKey, boardScope, onEditGoal, onDeleteGoal }: Props): JSX.Element {
  const [allOpen, setAllOpen] = useState(false)
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
        <p>No goals on this board yet. Use <strong>+ New goal</strong>, or <strong>Evaluate</strong> to analyze what's on this board into tasks, or let the planner seed a DAG.</p>
      </div>
    )
  }

  return (
    <div className={s.view}>
      {goals.length > 0 && (
        <button type="button" className={s.allDagBtn} onClick={() => setAllOpen(true)}>
          <Network size={13} /> View all goals &amp; tasks in one canvas
        </button>
      )}
      {goals.map((g) => (
        <GoalCard key={g.id} goal={g} tasks={tasksByGoal.get(g.id) ?? []} siblings={messages} boardKey={boardKey} boardScope={boardScope} onEditGoal={onEditGoal} onDeleteGoal={onDeleteGoal} />
      ))}
      {ungrouped.length > 0 && (
        <div className={s.ungrouped}>
          <div className={s.ungroupedHead}>Ungrouped tasks</div>
          {orderByDeps(ungrouped).map((t) => (
            <TaskCard key={t.id} task={t} siblings={messages} />
          ))}
        </div>
      )}
      {allOpen && (
        <GoalDetailModal messages={messages} initialGoalId="__all__" boardKey={boardKey} boardScope={boardScope} onClose={() => setAllOpen(false)} />
      )}
    </div>
  )
}
