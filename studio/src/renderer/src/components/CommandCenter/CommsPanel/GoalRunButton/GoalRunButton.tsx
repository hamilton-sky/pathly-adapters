import { useState } from 'react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import { GoalSelect } from './GoalSelect/GoalSelect'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
  CLI_KEY_GOAL,
  EDITOR_CLIS,
} from '../../../MarkdownEditor/EditorHeader/editorCli'
import s from './GoalRunButton.module.css'

type RunState = 'idle' | 'running' | 'busy' | 'done'

const EXECUTOR_OPTIONS = [
  { value: 'single', label: 'Single' },
  { value: 'loop',   label: 'Loop'   },
  { value: 'team',   label: 'Team'   },
]

const ADAPTER_OPTIONS = EDITOR_CLIS.map((c) => ({
  value: c.id,
  label: c.label,
  hint: c.unavailable ?? c.hint,
  disabled: !!c.unavailable,
}))

interface Props {
  goalId: string
  defaultExecutor?: string
}

// Run a goal's task-DAG. The user picks the executor (single|loop|team) AND the CLI
// engine (adapter) the run uses — one selector, two fields (ROADMAP multi-adapter rider).
// The adapter rides with the run to /comms/goals/run → start_goal_run → the spawn.
export function GoalRunButton({ goalId, defaultExecutor = 'single' }: Props): JSX.Element {
  const [executor, setExecutor] = useState(defaultExecutor)
  const [adapter, setAdapter] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_GOAL))

  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const runGoal = useCommsStore((st) => st.runGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const runState: RunState = (goalRunState[goalId] as RunState | undefined) ?? 'idle'
  const isActive = runState === 'running' || runState === 'busy'
  // `team` routes per-stage via the flow's adapter_map, so the per-goal engine pick
  // only applies to single/loop.
  const adapterApplies = executor !== 'team'

  const progress = useElapsedProgress(goalRunStart[goalId] || undefined)

  const pillState = runState === 'running' ? 'running'
    : runState === 'busy' ? 'busy'
    : runState === 'done' ? 'done'
    : 'idle'

  function handleAdapterChange(v: string): void {
    setAdapter(v as EditorCli)
    saveEditorCli(CLI_KEY_GOAL, v as EditorCli)
  }

  function handleRun(): void {
    runGoal(goalId, executor, {
      adapter: adapterApplies && adapter !== 'claude' ? adapter : undefined,
    })
  }

  return (
    <div className={s.root}>
      <div className={s.controls}>
        <GoalSelect
          value={executor}
          options={EXECUTOR_OPTIONS}
          onChange={setExecutor}
          ariaLabel="Executor"
          disabled={isActive}
          minWidth={68}
        />

        <GoalSelect
          value={adapter}
          options={ADAPTER_OPTIONS}
          onChange={handleAdapterChange}
          ariaLabel="CLI engine"
          disabled={isActive || !adapterApplies}
          minWidth={72}
        />

        <RunPill
          idleLabel="Run"
          state={pillState}
          progress={progress}
          onRun={handleRun}
          onStop={() => stopGoal(goalId)}
        />
      </div>
    </div>
  )
}
