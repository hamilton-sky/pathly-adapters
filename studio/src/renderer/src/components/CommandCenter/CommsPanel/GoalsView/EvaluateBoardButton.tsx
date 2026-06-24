import { useState, useRef } from 'react'
import { Sparkles, SlidersHorizontal, Square } from 'lucide-react'
import { Tooltip } from '../../../ui'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress, fmtElapsed } from '../../../shared/RunPill/progress'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
} from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { EvalConfigPopover } from './EvalConfigPopover'
import { EVAL_LENSES } from '../SingleAgentButton/agentFormData'
import s from './GoalsView.module.css'

// Persistent localStorage key for the evaluate button's engine choice.
const CLI_KEY_EVAL = 'pathly.comms.cli.eval'

interface Props {
  boardKey: string
}

// Two-zone button: [✦ Evaluate… 0:03] [⚙  or  ■ stop].
// The gear zone swaps to a stop button while the agent is running.
// EvalConfigPopover lets the user pick agent, skill, engine, and extra instructions.
export function EvaluateBoardButton({ boardKey }: Props): JSX.Element {
  const runEvaluator = useCommsStore((st) => st.runEvaluator)
  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)

  const runState = boardRunState[boardKey] ?? 'idle'
  const running = runState === 'running'
  const progress = useElapsedProgress(boardRunStart[boardKey] || undefined)

  const [selectedLens, setSelectedLens] = useState('')
  const [lensText, setLensText] = useState('')   // editable lens-prompt text
  const [extraPrompt, setExtraPrompt] = useState('')
  const [selectedCli, setSelectedCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_EVAL))
  const [configOpen, setConfigOpen] = useState(false)
  const gearRef = useRef<HTMLButtonElement>(null)

  const lensLabel = EVAL_LENSES.find((l) => l.name === selectedLens && l.name)?.label
  const activeLabel = lensLabel ?? 'Evaluate'
  const label =
    running ? (progress != null ? `${activeLabel}… ${fmtElapsed(progress.elapsedS)}` : `${activeLabel}…`)
    : runState === 'done' ? 'Done'
    : activeLabel

  function handleCliChange(cli: EditorCli): void {
    setSelectedCli(cli)
    saveEditorCli(CLI_KEY_EVAL, cli)
  }

  // Selecting a lens seeds the editable text; the user can then tweak it inline.
  function pickLens(name: string): void {
    setSelectedLens(name)
    setLensText(EVAL_LENSES.find((l) => l.name === name)?.prompt ?? '')
  }

  function handleRun(): void {
    const adapter = selectedCli !== 'claude' ? selectedCli : undefined
    runEvaluator(boardKey, {
      adapter,
      systemPrompt: lensText || undefined,
      instructions: extraPrompt || undefined,
    })
  }

  function handleConfigRun(): void {
    setConfigOpen(false)
    handleRun()
  }

  function handleReset(): void {
    setSelectedLens('')
    setLensText('')
    setExtraPrompt('')
  }

  return (
    <>
      <div className={s.evalRoot}>
        <Tooltip
          label={lensLabel ? `Evaluate board — ${lensLabel}` : 'Evaluate board'}
          description="Analyze everything on this board and propose concrete tasks"
          placement="bottom"
        >
          <button
            type="button"
            className={s.evalBtn}
            data-state={runState !== 'idle' ? runState : undefined}
            disabled={running}
            aria-label={label}
            onClick={handleRun}
          >
            <Sparkles size={13} />
            <span className={s.newGoalLabel}>{label}</span>
          </button>
        </Tooltip>

        {running ? (
          <Tooltip label="Stop the running agent" placement="bottom">
            <button type="button" className={s.evalStop} aria-label="Stop the running agent" onClick={() => stopBoard(boardKey)}>
              <Square size={11} />
            </button>
          </Tooltip>
        ) : (
          <Tooltip label="Configure evaluator" placement="bottom">
            <button
              ref={gearRef}
              type="button"
              className={s.evalGear}
              aria-label="Configure evaluator"
              {...(configOpen ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
              onClick={() => setConfigOpen((v) => !v)}
            >
              <SlidersHorizontal size={11} />
            </button>
          </Tooltip>
        )}
      </div>

      {configOpen && (
        <EvalConfigPopover
          anchorEl={gearRef.current}
          selectedLens={selectedLens}
          lensText={lensText}
          extraPrompt={extraPrompt}
          selectedCli={selectedCli}
          running={running}
          onSelectLens={pickLens}
          onLensTextChange={setLensText}
          onExtraPromptChange={setExtraPrompt}
          onCliChange={handleCliChange}
          onReset={handleReset}
          onRun={handleConfigRun}
          onClose={() => setConfigOpen(false)}
        />
      )}
    </>
  )
}
