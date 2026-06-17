import { useState } from 'react'
import { Boxes } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { useCommsStore } from '../../../../store/commsStore'
import type { DecomposeMode } from '../../../../store/commsApi'
import s from './GoalDecomposeButton.module.css'

type RunState = 'idle' | 'running' | 'busy' | 'done'

const MODE_LABELS: Record<DecomposeMode, string> = {
  planner: 'Planner (fast)',
  consultation: 'Consultation (deep)',
}

const LABEL: Record<RunState, string> = {
  idle: 'Decompose',
  running: 'Decomposing…',
  busy: 'Board busy',
  done: 'Done',
}

interface Props {
  goalId: string
}

// Shown on a goal that has no tasks yet — turns the goal into a task DAG via the
// planner (fast) or the consultation flow (deep). Reuses goalRunState for busy state.
export function GoalDecomposeButton({ goalId }: Props): JSX.Element {
  const [mode, setMode] = useState<DecomposeMode>('planner')
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'
  const isActive = runState === 'running' || runState === 'busy'

  return (
    <div className={s.root}>
      <select
        className={s.select}
        value={mode}
        aria-label="Decompose mode"
        disabled={isActive}
        onChange={(e) => setMode(e.currentTarget.value as DecomposeMode)}
      >
        {(Object.keys(MODE_LABELS) as DecomposeMode[]).map((m) => (
          <option key={m} value={m}>{MODE_LABELS[m]}</option>
        ))}
      </select>
      <Tooltip label="Decompose goal" description="Turn this goal into a task DAG the executors can run" placement="top">
        <button
          type="button"
          className={s.btn}
          data-state={runState !== 'idle' ? runState : undefined}
          disabled={runState === 'running'}
          aria-label={`Decompose goal with the ${mode}`}
          onClick={() => decomposeGoal(goalId, mode)}
        >
          <Boxes size={11} />
          <span className={s.label}>{LABEL[runState]}</span>
        </button>
      </Tooltip>
    </div>
  )
}
