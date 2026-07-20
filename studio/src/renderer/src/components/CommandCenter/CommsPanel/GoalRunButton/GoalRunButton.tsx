import { useState } from 'react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import { RunPill } from '../../../shared/RunPill/RunPill'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { ProgressSelect } from '../../../shared/ProgressSelect/ProgressSelect'
import { headingLayers } from '../../../../services/skillCompose'
import { GoalSelect } from './GoalSelect/GoalSelect'
import { useGoalRunPreview } from './useGoalRunPreview'
import { executorInfo } from './executorInfo'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
  cliLabel,
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
  /** Goal title + task rollup — shown in the send preview so the run is confirmed in context. */
  goalText?: string
  total?: number
  ready?: number
}

// Run a goal's task-DAG. The user picks the executor (single|loop|team) AND the CLI
// engine (adapter) the run uses — one selector, two fields (ROADMAP multi-adapter rider).
// The adapter rides with the run to /comms/goals/run → start_goal_run → the spawn.
// Run is preview-gated (SendPreviewModal), mirroring the board's Evaluate control.
export function GoalRunButton({ goalId, defaultExecutor = 'single', goalText = '', total = 0, ready = 0 }: Props): JSX.Element {
  const [executor, setExecutor] = useState(defaultExecutor)
  const [adapter, setAdapter] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_GOAL))
  const [confirmOpen, setConfirmOpen] = useState(false)
  // Per-run board-updates verbosity override; '' = inherit the Settings default.
  const [verbosity, setVerbosity] = useState('')

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

  const taskLine = `${total} task${total !== 1 ? 's' : ''} · ${ready} ready`
  const executorLabel = EXECUTOR_OPTIONS.find((o) => o.value === executor)?.label ?? executor
  const info = executorInfo(executor)
  const preview = useGoalRunPreview(confirmOpen, executor, goalText, taskLine)

  function handleAdapterChange(v: string): void {
    setAdapter(v as EditorCli)
    saveEditorCli(CLI_KEY_GOAL, v as EditorCli)
  }

  // Run is preview-gated: the pill opens the modal; confirming dispatches the run.
  function handleRun(): void {
    setConfirmOpen(true)
  }

  // Abilities + system-prompts are added in the Sections modal now. A Sections trim on the
  // 'single' executor (one drain-dag prompt) rides as prompt_override; loop/team are multi-spawn
  // (no single prompt), so their Sections output doesn't apply.
  function doRun(finalPrompt?: string, sectionsUsed?: boolean): void {
    setConfirmOpen(false)
    runGoal(goalId, executor, {
      adapter: adapterApplies && adapter !== 'claude' ? adapter : undefined,
      progress: verbosity || undefined,
      promptOverride: executor === 'single' && sectionsUsed ? finalPrompt : undefined,
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

      {/* Show which agent + skill the selected executor dispatches, live as it changes. */}
      <div className={s.hint} title="Agent and skill this executor sends">
        <span className={s.hintKey}>agent</span>
        <span className={s.hintValue}>{info.agent}</span>
        <span className={s.hintSep}>·</span>
        <span className={s.hintKey}>skill</span>
        <span className={s.hintValue}>{info.skill}</span>
      </div>

      {confirmOpen && (
        <SendPreviewModal
          title="Run goal"
          engineLabel={adapterApplies ? cliLabel(adapter) : 'per-stage (team)'}
          fileName={goalText || goalId}
          prompt={preview.prompt}
          readOnly
          headingLayers={headingLayers(preview.segments)}
          meta={[
            { label: 'Executor', value: executorLabel },
            { label: 'Agent', value: info.agent },
            { label: 'Skill', value: info.skill },
            { label: 'Tasks', value: taskLine },
          ]}
          submitLabel="Run"
          footerSlot={
            <ProgressSelect
              value={verbosity}
              onChange={setVerbosity}
              allowInherit
              disabled={isActive}
              label="Board updates"
              id="goalrun-progress"
            />
          }
          onSubmit={(finalPrompt, sectionsUsed) => doRun(finalPrompt, sectionsUsed)}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </div>
  )
}
