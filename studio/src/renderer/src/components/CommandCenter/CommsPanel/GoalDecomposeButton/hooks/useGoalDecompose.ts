import { useState, useRef } from 'react'
import { useCommsStore } from '../../../../../store/commsStore'
import { useElapsedProgress } from '../../../../shared/RunPill/progress'
import type { PillState } from '../../../../shared/RunPill/RunPill'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
} from '../../../../MarkdownEditor/EditorHeader/editorCli'
import type { DecomposeMode } from '../../../../../store/commsApi'

// Persistent localStorage key for the decompose button's engine choice (its own key so it
// is independent of the evaluator's — mirrors EvaluateBoardButton's CLI_KEY_EVAL).
const CLI_KEY_DECOMPOSE = 'pathly:goalDecomposeCli'

// UI state + handlers for GoalDecomposeButton, extracted so the component stays a thin view
// (mirrors how EvaluateBoardButton keeps its run logic local but small). Owns: mode, engine,
// popover/preview open state, the gear ref, and the run dispatch.
export function useGoalDecompose(goalId: string) {
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const runState = (goalRunState[goalId] ?? 'idle') as PillState
  const progress = useElapsedProgress(goalRunStart[goalId] || undefined)

  const [mode, setMode] = useState<DecomposeMode>('planner')
  const [selectedCli, setSelectedCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_DECOMPOSE))
  const [configOpen, setConfigOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const gearRef = useRef<HTMLButtonElement>(null)

  function handleCliChange(cli: EditorCli): void {
    setSelectedCli(cli)
    saveEditorCli(CLI_KEY_DECOMPOSE, cli)
  }

  function run(): void {
    const adapter = selectedCli !== 'claude' ? selectedCli : undefined
    decomposeGoal(goalId, mode, { adapter })
  }

  return {
    runState,
    progress,
    mode,
    setMode,
    selectedCli,
    handleCliChange,
    configOpen,
    setConfigOpen,
    confirmOpen,
    setConfirmOpen,
    gearRef,
    run,
    stop: () => stopGoal(goalId),
  }
}
