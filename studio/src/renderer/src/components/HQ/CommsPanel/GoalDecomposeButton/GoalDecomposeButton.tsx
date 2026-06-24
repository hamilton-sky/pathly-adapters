import { useState } from 'react'
import { Boxes } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { BoardSelect } from '../../../shared/BoardSelect/BoardSelect'
import { useCommsStore } from '../../../../store/commsStore'
import type { DecomposeMode } from '../../../../store/commsApi'
import s from './GoalDecomposeButton.module.css'

type RunState = 'idle' | 'running' | 'busy' | 'done'

// The two decompose modes. The hint line (shown in the dropdown) spells out how the
// mode relates to the Decompose action — fast/shallow vs deep/full-team — so the
// choice and the button read as one decision.
const MODE_OPTIONS = [
  { value: 'planner', label: 'Planner', hint: 'Fast · DAG only' },
  { value: 'consultation', label: 'Consultation', hint: 'Deep · full team' },
]

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
// planner (fast) or the consultation flow (deep). One connected control: the mode
// picker (left) and the Decompose action (right) share a single bordered frame so
// they read as a single "decompose, this way" decision (mirrors the Evaluate control).
export function GoalDecomposeButton({ goalId }: Props): JSX.Element {
  const [mode, setMode] = useState<DecomposeMode>('planner')
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'

  return (
    <div className={s.root} data-state={runState !== 'idle' ? runState : undefined}>
      <div className={s.modeZone}>
        <BoardSelect
          value={mode}
          options={MODE_OPTIONS}
          onChange={(v) => setMode(v as DecomposeMode)}
          ariaLabel="Decompose mode"
          triggerClassName={s.modeTrigger}
        />
      </div>
      <Tooltip label="Decompose goal" description="Turn this goal into a task DAG the executors can run" placement="top">
        <button
          type="button"
          className={s.btn}
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
