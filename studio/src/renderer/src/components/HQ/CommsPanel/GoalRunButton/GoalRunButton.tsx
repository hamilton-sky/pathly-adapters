import { useState } from 'react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import s from './GoalRunButton.module.css'

type RunState = 'idle' | 'running' | 'busy' | 'done'

const EXECUTOR_LABELS: Record<string, string> = {
  single: 'Single',
  loop: 'Loop',
  team: 'Team',
}

interface Props {
  goalId: string
  defaultExecutor?: string
}

export function GoalRunButton({ goalId, defaultExecutor = 'single' }: Props): JSX.Element {
  const [executor, setExecutor] = useState(defaultExecutor)

  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const runGoal = useCommsStore((st) => st.runGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'
  const isActive = runState === 'running' || runState === 'busy'

  const progress = useElapsedProgress(goalRunStart[goalId] || undefined)

  const pillState = runState === 'running' ? 'running'
    : runState === 'busy' ? 'busy'
    : runState === 'done' ? 'done'
    : 'idle'

  return (
    <div className={s.root}>
      <div className={s.controls}>
        <select
          className={s.select}
          value={executor}
          aria-label="Executor"
          onChange={(e) => setExecutor(e.currentTarget.value)}
          disabled={isActive}
        >
          {Object.keys(EXECUTOR_LABELS).map((ex) => (
            <option key={ex} value={ex}>{EXECUTOR_LABELS[ex]}</option>
          ))}
        </select>

        <RunPill
          idleLabel="Run"
          state={pillState}
          progress={progress}
          onRun={() => runGoal(goalId, executor)}
          onStop={() => stopGoal(goalId)}
        />
      </div>
    </div>
  )
}
