import { useState } from 'react'
import { Boxes } from 'lucide-react'
import { BoardSelect } from '../../../shared/BoardSelect/BoardSelect'
import { RunPill } from '../../../shared/RunPill/RunPill'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
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

interface Props {
  goalId: string
}

// Shown on a goal that has no tasks yet — turns the goal into a task DAG via the
// planner (fast) or the consultation flow (deep). Mode picker + the shared RunPill
// (timer + stop), so this spawn control reads the same as the goal Run control.
export function GoalDecomposeButton({ goalId }: Props): JSX.Element {
  const [mode, setMode] = useState<DecomposeMode>('planner')
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'
  const progress = useElapsedProgress(goalRunStart[goalId] || undefined)

  return (
    <div className={s.controls}>
      <div className={s.modeZone}>
        <BoardSelect
          value={mode}
          options={MODE_OPTIONS}
          onChange={(v) => setMode(v as DecomposeMode)}
          ariaLabel="Decompose mode"
          triggerClassName={s.modeTrigger}
        />
      </div>
      <RunPill
        idleLabel="Decompose"
        icon={<Boxes size={11} />}
        state={runState}
        progress={progress}
        onRun={() => decomposeGoal(goalId, mode)}
        onStop={() => stopGoal(goalId)}
      />
    </div>
  )
}
