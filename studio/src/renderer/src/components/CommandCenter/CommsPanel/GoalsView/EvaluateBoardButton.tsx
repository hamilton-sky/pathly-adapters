import { useState, useRef } from 'react'
import { Sparkles } from 'lucide-react'
import { useCommsStore } from '../../../../store/commsStore'
import { useElapsedProgress } from '../../../shared/RunPill/progress'
import type { PillState } from '../../../shared/RunPill/RunPill'
import ActionPill from '../../../shared/ActionPill/ActionPill'
import {
  type EditorCli,
  loadEditorCli,
  saveEditorCli,
  cliLabel,
} from '../.././../MarkdownEditor/EditorHeader/editorCli'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { EvalConfigPopover } from './EvalConfigPopover'
import { useEvaluatePreview } from './useEvaluatePreview'
import { EVAL_LENSES } from '../SingleAgentButton/agentFormData'

// Persistent localStorage key for the evaluate button's engine choice.
const CLI_KEY_EVAL = 'pathly.comms.cli.eval'

interface Props {
  boardKey: string
}

// Evaluate the board → propose tasks. Uses the shared ActionPill ([✦ Evaluate… 0:03][⚙↔■]),
// the same run+gear+stop control as the editor's AI Split/Analyze. The gear opens
// EvalConfigPopover (agent/skill/engine/extra), anchored to the gear button via gearRef.
export function EvaluateBoardButton({ boardKey }: Props): JSX.Element {
  const runEvaluator = useCommsStore((st) => st.runEvaluator)
  const stopBoard = useCommsStore((st) => st.stopBoard)
  const boardRunState = useCommsStore((st) => st.boardRunState)
  const boardRunStart = useCommsStore((st) => st.boardRunStart)

  const runState = (boardRunState[boardKey] ?? 'idle') as PillState
  const running = runState === 'running'
  const progress = useElapsedProgress(boardRunStart[boardKey] || undefined)

  const [selectedLens, setSelectedLens] = useState('')
  const [lensText, setLensText] = useState('')   // editable lens-prompt text
  const [extraPrompt, setExtraPrompt] = useState('')
  const [selectedCli, setSelectedCli] = useState<EditorCli>(() => loadEditorCli(CLI_KEY_EVAL))
  const [configOpen, setConfigOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const gearRef = useRef<HTMLButtonElement>(null)

  const lensLabel = EVAL_LENSES.find((l) => l.name === selectedLens && l.name)?.label
  const activeLabel = lensLabel ?? 'Evaluate'

  // Faithful read-only preview of the server-assembled evaluator prompt (fetched only
  // while the confirm modal is open).
  const previewPrompt = useEvaluatePreview(confirmOpen, lensText, extraPrompt)

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
      <ActionPill
        state={runState}
        progress={progress}
        hasPath
        title={activeLabel}
        runningVerb={activeLabel}
        mainIcon={<Sparkles size={13} />}
        idleTip={lensLabel
          ? `Evaluate board — ${lensLabel}`
          : 'Evaluate board — analyze everything and propose concrete tasks'}
        runningTip="Analyzing the board…"
        ariaName="Evaluate"
        onRun={() => setConfirmOpen(true)}
        onStop={() => stopBoard(boardKey)}
        configTip="Configure evaluator"
        onToggleConfig={() => setConfigOpen((v) => !v)}
        gearRef={gearRef}
      />

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

      {confirmOpen && (
        <SendPreviewModal
          title={activeLabel}
          engineLabel={cliLabel(selectedCli)}
          fileName={boardKey}
          prompt={previewPrompt}
          readOnly
          meta={[{ label: 'Lens', value: lensLabel ?? 'Built-in evaluator' }]}
          submitLabel="Run Evaluate"
          onSubmit={() => { setConfirmOpen(false); handleRun() }}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </>
  )
}
