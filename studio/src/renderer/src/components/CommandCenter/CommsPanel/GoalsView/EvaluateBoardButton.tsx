import { Sparkles } from 'lucide-react'
import ActionPill from '../../../shared/ActionPill/ActionPill'
import SendPreviewModal from '../../../shared/SendPreviewModal/SendPreviewModal'
import { ConfirmModal } from '../../../shared/ConfirmModal/ConfirmModal'
import { ProgressSelect } from '../../../shared/ProgressSelect/ProgressSelect'
import { cliLabel } from '../.././../MarkdownEditor/EditorHeader/editorCli'
import { EvalConfigPopover } from './EvalConfigPopover'
import { useEvaluateBoardButton } from './hooks/useEvaluateBoardButton'

export interface GoalStub {
  id: string
  text: string
}

interface Props {
  boardKey: string
  /** Goals on this board — used to populate the Target selector in the popover. */
  goals?: GoalStub[]
}

// Evaluate the board → propose tasks. Also dispatches per-goal decompose when the
// user picks a specific goal as the target. Uses the shared ActionPill, the same
// run+gear+stop control as the editor's AI Split/Analyze. The gear opens
// EvalConfigPopover (rigor, target, lens, engine). All state + handlers live in
// useEvaluateBoardButton; this component is the JSX shell.
export function EvaluateBoardButton({ boardKey, goals = [] }: Props): JSX.Element {
  const e = useEvaluateBoardButton(boardKey)

  return (
    <>
      <ActionPill
        state={e.runState}
        progress={e.progress}
        hasPath
        title={e.activeLabel}
        runningVerb={e.targetGoalId ? 'Planning' : e.activeLabel}
        mainIcon={<Sparkles size={13} />}
        idleTip={e.lensLabel
          ? `Evaluate board — ${e.lensLabel}`
          : 'Evaluate board — analyze everything and propose concrete tasks'}
        runningTip={e.targetGoalId ? 'Planning goal…' : 'Analyzing the board…'}
        ariaName="Evaluate"
        onRun={e.onPillRun}
        onStop={e.handleStop}
        configTip="Configure evaluator"
        onToggleConfig={() => e.setConfigOpen((v) => !v)}
        gearRef={e.gearRef}
      />

      {e.configOpen && (
        <EvalConfigPopover
          anchorEl={e.gearRef.current}
          selectedLens={e.selectedLens}
          lensText={e.lensText}
          extraPrompt={e.extraPrompt}
          selectedCli={e.selectedCli}
          running={e.running}
          goals={goals}
          targetGoalId={e.targetGoalId}
          rigorMode={e.rigorMode}
          onSelectLens={e.pickLens}
          onLensTextChange={e.setLensText}
          onExtraPromptChange={e.setExtraPrompt}
          onCliChange={e.handleCliChange}
          onTargetChange={e.setTargetGoalId}
          onRigorChange={e.setRigorMode}
          featureRigor={e.featureRigor}
          onFeatureRigorChange={e.setFeatureRigor}
          onFeatureDecompose={e.dispatchFeatureDecompose}
          onReset={e.handleReset}
          onRun={e.onConfigRun}
          onClose={() => e.setConfigOpen(false)}
        />
      )}

      {e.confirmOpen && !e.targetGoalId && (
        <SendPreviewModal
          title={e.activeLabel}
          engineLabel={cliLabel(e.selectedCli)}
          fileName={boardKey}
          prompt={e.previewPrompt}
          readOnly
          meta={[{ label: 'Lens', value: e.lensLabel ?? 'Built-in evaluator' }]}
          submitLabel="Run Evaluate"
          footerSlot={<ProgressSelect value={e.verbosity} onChange={e.setVerbosity} allowInherit label="Board updates" id="eval-progress" />}
          onSubmit={e.confirmWholeBoard}
          onCancel={e.cancelWholeBoard}
        />
      )}

      {e.confirmGoalOpen && e.targetGoalId && (
        <ConfirmModal
          title="Run a full consultation?"
          message="Consultation decomposes this goal with the full team (PO → architect → research → design → planner). It spawns several agents and can take a while before the task DAG appears."
          confirmLabel="Run consultation"
          footerSlot={<ProgressSelect value={e.verbosity} onChange={e.setVerbosity} allowInherit label="Board updates" id="consult-progress" />}
          onConfirm={e.confirmGoal}
          onCancel={e.cancelGoal}
        />
      )}
    </>
  )
}
