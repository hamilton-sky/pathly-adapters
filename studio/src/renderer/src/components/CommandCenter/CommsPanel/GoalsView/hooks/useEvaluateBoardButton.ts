import { useRef, useState } from 'react'
import { useCommsStore } from '../../../../../store/commsStore'
import { useElapsedProgress } from '../../../../shared/RunPill/progress'
import type { PillState } from '../../../../shared/RunPill/RunPill'
import type { DecomposeMode } from '../../../../../store/commsApi'
import { type EditorCli, loadEditorCli, saveEditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import { useEvaluatePreview } from '../useEvaluatePreview'
import { EVAL_LENSES } from '../../SingleAgentButton/agentFormData'

// Persistent localStorage key for the evaluate button's engine choice.
const CLI_KEY_EVAL = 'pathly.comms.cli.eval'

/**
 * All state + derived values + handlers for EvaluateBoardButton. The component is left
 * as pure JSX. Handles two dispatch altitudes off one control: whole-board evaluate
 * (preview-gated) and per-goal decompose (consultation-gated), plus the pill/timer and
 * the target-lock that keeps a live run from desyncing when the popover is reopened.
 */
export function useEvaluateBoardButton(boardKey: string) {
  const runEvaluator = useCommsStore((st) => st.runEvaluator)
  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)
  const stopGoal = useCommsStore((st) => st.stopGoal)

  const [selectedLens, setSelectedLens] = useState('')
  const [lensText, setLensText] = useState('')
  const [extraPrompt, setExtraPrompt] = useState('')
  const [selectedCli, setSelectedCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_EVAL))
  const [configOpen, setConfigOpen] = useState(false)
  // Whole-board preview gate (SendPreviewModal) vs goal consultation gate (ConfirmModal).
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmGoalOpen, setConfirmGoalOpen] = useState(false)
  // '' = whole board; otherwise = a goal id.
  const [targetGoalId, setTargetGoalId] = useState('')
  const [rigorMode, setRigorMode] = useState<DecomposeMode>('plan')
  const gearRef = useRef<HTMLButtonElement>(null)

  // Pill state: when a specific goal is targeted, reflect its decompose state instead.
  const runState: PillState = targetGoalId
    ? ((goalRunState[targetGoalId] ?? 'idle') as PillState)
    : ((boardRunState[boardKey] ?? 'idle') as PillState)
  const running = runState === 'running'

  // Elapsed clock: board start for whole-board runs, the goal's own start for goal runs.
  const boardProgress = useElapsedProgress(boardRunStart[boardKey] || undefined)
  const goalProgress = useElapsedProgress(
    targetGoalId ? goalRunStart[targetGoalId] || undefined : undefined,
  )
  const progress = targetGoalId ? goalProgress : boardProgress

  const lensLabel = EVAL_LENSES.find((l) => l.name === selectedLens && l.name)?.label
  const activeLabel = lensLabel ?? 'Evaluate'

  const previewPrompt = useEvaluatePreview(confirmOpen && !targetGoalId, lensText, extraPrompt)

  function handleCliChange(cli: EditorCli): void {
    setSelectedCli(cli)
    saveEditorCli(CLI_KEY_EVAL, cli)
  }

  function pickLens(name: string): void {
    setSelectedLens(name)
    setLensText(EVAL_LENSES.find((l) => l.name === name)?.prompt ?? '')
  }

  // The actual dispatch — no gating. Goal target → decompose; else → whole-board evaluate.
  function dispatch(): void {
    const adapter = selectedCli !== 'claude' ? selectedCli : undefined
    if (targetGoalId) {
      decomposeGoal(targetGoalId, rigorMode, { adapter })
    } else {
      runEvaluator(boardKey, {
        adapter,
        systemPrompt: lensText || undefined,
        instructions: extraPrompt || undefined,
      })
    }
  }

  // Goal decompose is gated only for the heavy consultation tier (full team run); quick/full
  // dispatch immediately. Returns having either dispatched or opened the confirm gate.
  function requestGoalRun(): void {
    if (rigorMode === 'consultation') setConfirmGoalOpen(true)
    else dispatch()
  }

  // Main pill: whole board → preview modal; goal → consultation gate or direct dispatch.
  function onPillRun(): void {
    if (targetGoalId) requestGoalRun()
    else setConfirmOpen(true)
  }

  // Gear popover primary: the config surface already stands in for a preview, so whole-board
  // dispatches directly here; the goal path still gates consultation.
  function onConfigRun(): void {
    setConfigOpen(false)
    if (targetGoalId) requestGoalRun()
    else dispatch()
  }

  function handleStop(): void {
    if (targetGoalId) stopGoal(targetGoalId)
    else stopBoard(boardKey)
  }

  function handleReset(): void {
    setSelectedLens('')
    setLensText('')
    setExtraPrompt('')
  }

  return {
    // config values
    selectedLens, lensText, extraPrompt, selectedCli, targetGoalId, rigorMode,
    // pill
    runState, running, progress, activeLabel, lensLabel,
    // popover / modal open state
    configOpen, setConfigOpen, confirmOpen, confirmGoalOpen, gearRef,
    // preview
    previewPrompt,
    // handlers
    handleCliChange, pickLens, setLensText, setExtraPrompt, setTargetGoalId, setRigorMode,
    handleReset, handleStop, onPillRun, onConfigRun, dispatch,
    confirmWholeBoard: () => { setConfirmOpen(false); dispatch() },
    cancelWholeBoard: () => setConfirmOpen(false),
    confirmGoal: () => { setConfirmGoalOpen(false); dispatch() },
    cancelGoal: () => setConfirmGoalOpen(false),
  }
}
