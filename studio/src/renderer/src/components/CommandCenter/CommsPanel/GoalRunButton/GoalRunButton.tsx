import { useState } from 'react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
  EDITOR_CLIS,
  CLI_KEY_GOAL,
} from '../../../MarkdownEditor/EditorHeader/editorCli'
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

  function handleAdapterChange(v: EditorCli): void {
    setAdapter(v)
    saveEditorCli(CLI_KEY_GOAL, v)
  }

  function handleRun(): void {
    runGoal(goalId, executor, {
      adapter: adapterApplies && adapter !== 'claude' ? adapter : undefined,
    })
  }

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

        <select
          className={s.select}
          value={adapter}
          aria-label="CLI engine"
          title={adapterApplies ? 'CLI engine for this goal' : "Team uses the flow’s per-stage routing"}
          onChange={(e) => handleAdapterChange(e.currentTarget.value as EditorCli)}
          disabled={isActive || !adapterApplies}
        >
          {EDITOR_CLIS.map((c) => (
            <option key={c.id} value={c.id} disabled={!!c.unavailable}>
              {c.label}{c.unavailable ? ' (n/a)' : ''}
            </option>
          ))}
        </select>

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
