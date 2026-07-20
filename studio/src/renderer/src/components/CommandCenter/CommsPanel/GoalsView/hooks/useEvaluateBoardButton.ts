import { useRef, useState } from 'react'
import { useCommsStore } from '../../../../../store/commsStore'
import { useElapsedProgress } from '../../../../shared/RunPill/progress'
import type { PillState } from '../../../../shared/RunPill/RunPill'
import type { DecomposeMode } from '../../../../../store/commsApi'
import type { BoardScope } from '../../../types'
import { type EditorCli, loadEditorCli, saveEditorCli } from '../../../../MarkdownEditor/EditorHeader/editorCli'
import { useEvaluatePreview } from '../useEvaluatePreview'
import { EVAL_LENSES } from '../../SingleAgentButton/agentFormData'
import { DECOMPOSE_TARGET, type FeatureRigor } from '../FeatureDecomposeConfig/FeatureDecomposeConfig'

// Persistent localStorage key for the evaluate button's engine choice.
const CLI_KEY_EVAL = 'pathly.comms.cli.eval'

/**
 * All state + derived values + handlers for EvaluateBoardButton. The component is left
 * as pure JSX. Handles three explicit actions off one control: whole-board evaluate
 * (preview-gated), whole-board decompose into goals (consultation-gated), and per-goal
 * decompose into tasks (consultation-gated) — plus the pill/timer and the target-lock
 * that keeps a live run from desyncing when the popover is reopened.
 */
export function useEvaluateBoardButton(boardKey: string, boardScope?: BoardScope) {
  const runEvaluator = useCommsStore((st) => st.runEvaluator)
  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)
  const goalRunState = useCommsStore((st) => st.goalRunState)
  const goalRunStart = useCommsStore((st) => st.goalRunStart)
  const decomposeGoal = useCommsStore((st) => st.decomposeGoal)
  const decomposeFeature = useCommsStore((st) => st.decomposeFeature)
  const decomposeProject = useCommsStore((st) => st.decomposeProject)
  const stopGoal = useCommsStore((st) => st.stopGoal)
  const isProjectBoard = boardScope === 'project'

  const [selectedLens, setSelectedLens] = useState('')
  const [lensText, setLensText] = useState('')
  const [extraPrompt, setExtraPrompt] = useState('')
  const [selectedCli, setSelectedCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_EVAL))
  const [configOpen, setConfigOpen] = useState(false)
  // Whole-board preview gate (SendPreviewModal) vs goal/feature consultation gates (ConfirmModal).
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmGoalOpen, setConfirmGoalOpen] = useState(false)
  const [confirmFeatureOpen, setConfirmFeatureOpen] = useState(false)
  // '' = whole-board evaluate; DECOMPOSE_TARGET = whole-board decompose into goals;
  // otherwise = a goal id (decompose into tasks).
  const [targetGoalId, setTargetGoalId] = useState('')
  const [rigorMode, setRigorMode] = useState<DecomposeMode>('plan')
  // Whole-board "Decompose into goals" rigor (light/full/consultation) — distinct from the
  // per-goal rigorMode above.
  const [featureRigor, setFeatureRigor] = useState<FeatureRigor>('light')
  // Per-run board-updates verbosity override; '' = inherit the Settings default.
  const [verbosity, setVerbosity] = useState('')
  const gearRef = useRef<HTMLButtonElement>(null)

  // Three targets, two run-state homes: a real goal tracks its own decompose state;
  // whole-board evaluate AND whole-board decompose both track the board run state
  // (decomposeFeature marks boardRunState/boardRunStart, same as runEvaluator).
  const isDecomposeTarget = targetGoalId === DECOMPOSE_TARGET
  const isGoalTarget = Boolean(targetGoalId) && !isDecomposeTarget
  const runState: PillState = isGoalTarget
    ? ((goalRunState[targetGoalId] ?? 'idle') as PillState)
    : ((boardRunState[boardKey] ?? 'idle') as PillState)
  const running = runState === 'running'

  // Elapsed clock: board start for whole-board runs, the goal's own start for goal runs.
  const boardProgress = useElapsedProgress(boardRunStart[boardKey] || undefined)
  const goalProgress = useElapsedProgress(
    isGoalTarget ? goalRunStart[targetGoalId] || undefined : undefined,
  )
  const progress = isGoalTarget ? goalProgress : boardProgress

  const lensLabel = EVAL_LENSES.find((l) => l.name === selectedLens && l.name)?.label
  const activeLabel = isDecomposeTarget ? 'Decompose' : (lensLabel ?? 'Evaluate')

  const evalPreview = useEvaluatePreview(
    confirmOpen && !targetGoalId,
    lensText,
    extraPrompt,
  )
  const previewPrompt = evalPreview.prompt
  const previewSegments = evalPreview.segments

  function handleCliChange(cli: EditorCli): void {
    setSelectedCli(cli)
    saveEditorCli(CLI_KEY_EVAL, cli)
  }

  function pickLens(name: string): void {
    setSelectedLens(name)
    setLensText(EVAL_LENSES.find((l) => l.name === name)?.prompt ?? '')
  }

  // The actual dispatch. Goal target → decompose; else → whole-board evaluate. finalPrompt is the
  // gate's Sections-trimmed prompt (whole-board only): sent as prompt_override, with lens/extra
  // already baked into it (so they are NOT also sent as system/instructions — no duplication).
  function dispatch(finalPrompt?: string): void {
    const adapter = selectedCli !== 'claude' ? selectedCli : undefined
    if (isGoalTarget) {
      // finalPrompt is already gated on sectionsUsed by confirmWholeBoard — so a plain
      // "Run decompose" sends no override (server composes) while a Sections trim sends the
      // full planner prompt verbatim (abilities + system-prompts already folded in via Sections).
      decomposeGoal(targetGoalId, rigorMode, {
        adapter,
        progress: verbosity || undefined,
        promptOverride: finalPrompt,
      })
    } else if (finalPrompt) {
      runEvaluator(boardKey, {
        adapter,
        promptOverride: finalPrompt,
        progress: verbosity || undefined,
      })
    } else {
      runEvaluator(boardKey, {
        adapter,
        systemPrompt: lensText || undefined,
        instructions: extraPrompt || undefined,
        progress: verbosity || undefined,
      })
    }
  }

  // Whole-board "Decompose into goals/features" — ungated dispatch, called after any
  // consultation gate has been passed. The project board decomposes into sibling
  // FEATURES one altitude up; every other board decomposes into sibling goals.
  function dispatchFeatureDecompose(): void {
    const adapter = selectedCli !== 'claude' ? selectedCli : undefined
    if (isProjectBoard) decomposeProject(boardKey, featureRigor, { adapter })
    else decomposeFeature(boardKey, featureRigor, { adapter })
  }

  // Feature decompose is gated for the heavy consultation tier (full team run), mirroring
  // the goal path; light/full dispatch immediately.
  function requestFeatureDecompose(): void {
    setConfigOpen(false)
    if (featureRigor === 'consultation') setConfirmFeatureOpen(true)
    else dispatchFeatureDecompose()
  }

  // Goal decompose: the heavy consultation tier opens the consultation confirm; quick/full (the
  // decompose planner) now open the SendPreviewModal preview gate — the same one whole-board
  // evaluate uses — so no decompose spawns without a prompt preview first. confirmWholeBoard
  // calls dispatch(), which already routes a goal target to decomposeGoal.
  function requestGoalRun(): void {
    if (rigorMode === 'consultation') setConfirmGoalOpen(true)
    else setConfirmOpen(true)
  }

  // Main pill: board evaluate → preview modal; board decompose → consultation gate or direct
  // dispatch; goal → consultation gate or direct dispatch.
  function onPillRun(): void {
    if (isDecomposeTarget) requestFeatureDecompose()
    else if (isGoalTarget) requestGoalRun()
    else setConfirmOpen(true)
  }

  // Gear popover primary: "Run now" opens the same guard modal as the pill (setConfirmOpen) so
  // the board-updates override + prompt preview are shown before the CLI engine spawns; the goal
  // path still gates consultation (light/full goal tiers dispatch directly, inheriting the default).
  function onConfigRun(): void {
    setConfigOpen(false)
    if (isGoalTarget) requestGoalRun()
    else setConfirmOpen(true)
  }

  function handleStop(): void {
    if (isGoalTarget) stopGoal(targetGoalId)
    else stopBoard(boardKey)
  }

  function handleReset(): void {
    setSelectedLens('')
    setLensText('')
    setExtraPrompt('')
  }

  return {
    // config values
    selectedLens, lensText, extraPrompt, selectedCli, targetGoalId, rigorMode, verbosity,
    featureRigor, setFeatureRigor, requestFeatureDecompose,
    // derived target kind
    isDecomposeTarget, isGoalTarget, isProjectBoard,
    // pill
    runState, running, progress, activeLabel, lensLabel,
    // popover / modal open state
    configOpen, setConfigOpen, confirmOpen, confirmGoalOpen, confirmFeatureOpen, gearRef,
    // preview
    previewPrompt, previewSegments,
    // handlers
    handleCliChange, pickLens, setLensText, setExtraPrompt, setTargetGoalId, setRigorMode, setVerbosity,
    handleReset, handleStop, onPillRun, onConfigRun, dispatch,
    // Only a CONFIRMED Sections config overrides composition — a plain "Run Evaluate" must
    // leave it to the server, else the run ships a body without the platform fragments
    // (no BOARD_EVAL post, no AGENT_DONE → vanishes from RECENT and goes unbilled).
    confirmWholeBoard: (finalPrompt?: string, sectionsUsed?: boolean) => {
      setConfirmOpen(false)
      dispatch(sectionsUsed ? finalPrompt : undefined)
    },
    cancelWholeBoard: () => setConfirmOpen(false),
    confirmGoal: () => { setConfirmGoalOpen(false); dispatch() },
    cancelGoal: () => setConfirmGoalOpen(false),
    confirmFeature: () => { setConfirmFeatureOpen(false); dispatchFeatureDecompose() },
    cancelFeature: () => setConfirmFeatureOpen(false),
  }
}
