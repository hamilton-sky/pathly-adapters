import { useState } from 'react'
import { Play, Square } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { useCommsStore } from '../../../../store/commsStore'
import s from './GoalRunButton.module.css'

type Executor = 'single' | 'loop' | 'team'
type RunState = 'idle' | 'running' | 'busy' | 'done'

const EXECUTOR_LABELS: Record<Executor, string> = {
  single: 'Single',
  loop: 'Loop',
  team: 'Team',
}

const RUN_LABEL: Record<RunState, string> = {
  idle: 'Run',
  running: 'Running…',
  busy: 'Board busy',
  done: 'Done',
}

interface Props {
  goalId: string
  defaultExecutor?: Executor
}

export function GoalRunButton({ goalId, defaultExecutor = 'single' }: Props): JSX.Element {
  const [executor, setExecutor] = useState<Executor>(defaultExecutor)

  const goalRunState = useCommsStore((st) => st.goalRunState)
  const runGoal = useCommsStore((st) => st.runGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'
  const isRunning = runState === 'running'
  const isActive = runState === 'running' || runState === 'busy'

  function handleRun(): void {
    runGoal(goalId, executor)
  }

  function handleStop(): void {
    stopGoal(goalId)
  }

  return (
    <div className={s.root}>
      <div className={s.controls}>
        <select
          className={s.select}
          value={executor}
          aria-label="Executor"
          onChange={(e) => setExecutor(e.currentTarget.value as Executor)}
          disabled={isActive}
        >
          {(Object.keys(EXECUTOR_LABELS) as Executor[]).map((ex) => (
            <option key={ex} value={ex}>{EXECUTOR_LABELS[ex]}</option>
          ))}
        </select>

        <div className={s.group}>
          <Tooltip label="Run goal" description={`Run this goal with the ${EXECUTOR_LABELS[executor]} executor`} placement="top">
            <button
              type="button"
              className={s.runBtn}
              data-state={runState !== 'idle' ? runState : undefined}
              disabled={isRunning}
              aria-label={`Run goal with ${executor} executor`}
              onClick={handleRun}
            >
              <Play size={10} />
              <span className={s.runLabel}>{RUN_LABEL[runState]}</span>
            </button>
          </Tooltip>
          <Tooltip label="Stop run" placement="top">
            <button
              type="button"
              className={s.stopBtn}
              disabled={!isActive}
              aria-label="Stop goal run"
              onClick={handleStop}
            >
              <Square size={9} />
            </button>
          </Tooltip>
        </div>
      </div>
    </div>
  )
}
